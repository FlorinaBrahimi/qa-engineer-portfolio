"""Submission Service HTTP API and minimal web UI.

Run locally:  python -m app.server   (listens on PORT, default 5001)
On AWS the same app is served by Lambda through aws/app_handler.py.

Endpoints
---------
GET  /health                      liveness probe
GET  /api/openapi.json            machine-readable contract (consumed by ai_testing/)
GET  /api/submissions             list submissions          (requires X-API-Key)
POST /api/submissions             create submission         (requires X-API-Key)
GET  /api/submissions/<id>        fetch one                 (requires X-API-Key)
DELETE /api/submissions/<id>      delete one                (requires X-API-Key)
GET  /                            HTML form + results table
GET  /accessibility               accessibility statement
POST /submit                      HTML form handler

Storage is pluggable (app/storage.py): in-memory by default, DynamoDB when
STORAGE_BACKEND=dynamodb.
"""
from __future__ import annotations

import hmac
import logging
import os
import uuid
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.serving import WSGIRequestHandler

from app.similarity import similarity_band, similarity_score, word_count
from app.storage import build_store

DEFAULT_API_KEY = "qa-demo-key"   # for local, Docker and CI runs only; never valid on AWS
API_KEY = os.environ.get("SUBMISSION_API_KEY", DEFAULT_API_KEY)
ON_AWS = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
MIN_TEXT_LENGTH = 20
MAX_TEXT_LENGTH = 20_000
MAX_TITLE_LENGTH = 200
MAX_AUTHOR_LENGTH = 200
MAX_BODY_BYTES = 256 * 1024       # largest valid JSON body is about 80 KB; refuse far beyond that
MAX_PAGE_SIZE = 500

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
store = build_store()
audit_log = logging.getLogger("submission_service.audit")

# The development server adds its own "Server: Werkzeug/x Python/y" header. Replace it at the
# source so no response discloses the stack (OWASP Secure Headers; first raised as DEF-104).
WSGIRequestHandler.server_version = "submission-service"
WSGIRequestHandler.sys_version = ""
WSGIRequestHandler.version_string = lambda self: "submission-service"
app.jinja_env.filters["band"] = similarity_band


def page_context(items: list[dict], errors: dict | None = None, form: dict | None = None) -> dict:
    """Everything index.html needs: rows, validation state, and summary stats."""
    flagged = sum(1 for s in items if s["status"] == "flagged")
    average = round(sum(s["similarity_score"] for s in items) / len(items), 1) if items else 0.0
    return {
        "items": items,
        "errors": errors or {},
        "form": form or {},
        "stats": {"total": len(items), "flagged": flagged, "average": average},
        "min_text_length": MIN_TEXT_LENGTH,
        "backend_label": "Cloud" if type(store).__name__ == "DynamoStore" else "Local",
    }


CSP = "; ".join([
    "default-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


@app.after_request
def security_headers(response):
    """Headers recommended by the OWASP Secure Headers Project."""
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Content-Security-Policy"] = CSP
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    h["Cross-Origin-Resource-Policy"] = "same-origin"
    h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    # Submissions are personal work. Never let a shared cache or the browser keep API or page
    # responses; static assets carry no user data and may be cached.
    if not request.path.startswith("/static/"):
        h["Cache-Control"] = "no-store"
    return response


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.path == "/health"


@app.errorhandler(HTTPException)
def http_error(exc: HTTPException):
    """API clients always get JSON, never a framework HTML page."""
    if _wants_json():
        codes = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 413: "payload_too_large", 415: "unsupported_media_type"}
        return jsonify({"error": codes.get(exc.code, "error")}), exc.code
    return exc


@app.errorhandler(Exception)
def unexpected_error(exc: Exception):
    """Fail safely: log the detail server-side, tell the client nothing about internals."""
    app.logger.exception("unhandled error on %s %s", request.method, request.path)
    if _wants_json():
        return jsonify({"error": "internal_error"}), 500
    return "Something went wrong.", 500


def _client_ip() -> str:
    return (request.headers.get("X-Forwarded-For", request.remote_addr or "") or "").split(",")[0].strip()


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        supplied = request.headers.get("X-API-Key", "")
        # A deployment that still has the public default key is misconfigured: refuse everything.
        misconfigured = ON_AWS and API_KEY == DEFAULT_API_KEY
        # compare_digest takes the same time whether the first or last character differs,
        # so response timing cannot be used to guess the key one character at a time.
        valid = hmac.compare_digest(supplied.encode(), API_KEY.encode()) and not misconfigured
        if not valid:
            # Audit trail for failed authentication. The supplied key is never logged.
            audit_log.warning(
                "auth_failed method=%s path=%s ip=%s key_supplied=%s",
                request.method, request.path, _client_ip(), bool(supplied),
            )
            return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)

    return wrapper


def validate(payload: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    # Reject non-string values up front. Without this, a number or list reached .strip()
    # and crashed with a 500 (DEF-106, found by an AI-generated test).
    for field in ("title", "author", "text"):
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            errors[field] = f"{field} must be a string"
    if errors:
        return errors
    title = (payload.get("title") or "").strip()
    author = (payload.get("author") or "").strip()
    text = payload.get("text") or ""
    if not title:
        errors["title"] = "title is required"
    elif len(title) > MAX_TITLE_LENGTH:
        errors["title"] = f"title must be {MAX_TITLE_LENGTH} characters or fewer"
    if not author:
        errors["author"] = "author is required"
    elif len(author) > MAX_AUTHOR_LENGTH:
        errors["author"] = f"author must be {MAX_AUTHOR_LENGTH} characters or fewer"
    if len(text.strip()) < MIN_TEXT_LENGTH:
        errors["text"] = f"text must be at least {MIN_TEXT_LENGTH} characters"
    elif len(text) > MAX_TEXT_LENGTH:
        errors["text"] = f"text must be at most {MAX_TEXT_LENGTH} characters"
    return errors


def build_submission(payload: dict) -> dict:
    score = similarity_score(payload["text"])
    return {
        "id": str(uuid.uuid4()),
        "title": payload["title"].strip(),
        "author": payload["author"].strip(),
        "word_count": word_count(payload["text"]),
        "similarity_score": score,
        "status": "flagged" if score >= 25.0 else "clear",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
def health():
    return jsonify({"status": "ok", "submissions": store.count(), "backend": type(store).__name__})


@app.get("/api/openapi.json")
def openapi():
    return jsonify(
        {
            "openapi": "3.0.0",
            "info": {"title": "Submission Service", "version": "1.0.0"},
            "components": {"securitySchemes": {"ApiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}}},
            "paths": {
                "/api/submissions": {
                    "get": {"summary": "List submissions", "responses": {"200": {}, "401": {}}},
                    "post": {
                        "summary": "Create submission",
                        "requestBody": {
                            "required": ["title", "author", "text"],
                            "constraints": {
                                "title": "1-200 chars",
                                "author": "1-200 chars",
                                "text": f"{MIN_TEXT_LENGTH}-{MAX_TEXT_LENGTH} chars",
                            },
                        },
                        "responses": {"201": {}, "400": {}, "401": {}},
                    },
                },
                "/api/submissions/{id}": {
                    "get": {"summary": "Get submission", "responses": {"200": {}, "401": {}, "404": {}}},
                    "delete": {"summary": "Delete submission", "responses": {"204": {}, "401": {}, "404": {}}},
                },
            },
        }
    )


@app.get("/api/submissions")
@require_api_key
def list_submissions():
    """Bounded listing: a client can never make the service return an unbounded response."""
    raw = request.args.get("limit", str(MAX_PAGE_SIZE))
    if not raw.isdigit() or not 1 <= int(raw) <= MAX_PAGE_SIZE:
        return jsonify({"error": "validation_failed", "fields": {"limit": f"limit must be a whole number from 1 to {MAX_PAGE_SIZE}"}}), 400
    everything = store.list()
    items = everything[: int(raw)]
    return jsonify({"items": items, "count": len(items), "total": len(everything)})


@app.post("/api/submissions")
@require_api_key
def create_submission():
    if not request.is_json:
        return jsonify({"error": "unsupported_media_type"}), 415
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "body must be a JSON object"}), 400
    errors = validate(payload)
    if errors:
        return jsonify({"error": "validation_failed", "fields": errors}), 400
    submission = build_submission(payload)
    store.put(submission)
    return jsonify(submission), 201


@app.get("/api/submissions/<submission_id>")
@require_api_key
def get_submission(submission_id: str):
    submission = store.get(submission_id)
    if submission is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(submission)


@app.delete("/api/submissions/<submission_id>")
@require_api_key
def delete_submission(submission_id: str):
    if not store.delete(submission_id):
        return jsonify({"error": "not_found"}), 404
    return "", 204


@app.get("/")
def index():
    # After a successful form post we redirect here with ?added=<id> so the page can confirm
    # the result in a status message that assistive technology announces (WCAG 4.1.3).
    added = store.get(request.args.get("added", "")) if request.args.get("added") else None
    return render_template("index.html", **page_context(store.list()), added=added)


def _same_origin() -> bool:
    """Refuse form posts that another website triggered (CSRF defence).

    Browsers label every request with Sec-Fetch-Site (Fetch Metadata), which a page cannot
    forge. "cross-site" means a different site made the browser send this. Older browsers
    without that header fall back to the Origin check. Origin alone is not enough here: the
    strict Referrer-Policy makes browsers send "Origin: null" on this site's own form.
    """
    site = request.headers.get("Sec-Fetch-Site")
    if site is not None:
        return site in ("same-origin", "none")
    origin = request.headers.get("Origin")
    return origin in (None, "null") or urlparse(origin).netloc == request.host


@app.post("/submit")
def submit_form():
    if not _same_origin():
        audit_log.warning("cross_site_form_post_blocked site=%s origin=%s ip=%s", request.headers.get("Sec-Fetch-Site"), request.headers.get("Origin"), _client_ip())
        return "Cross-site form submission refused.", 403
    payload = {k: request.form.get(k, "") for k in ("title", "author", "text")}
    errors = validate(payload)
    if errors:
        return render_template("index.html", **page_context(store.list(), errors, payload)), 400
    submission = build_submission(payload)
    store.put(submission)
    return redirect(url_for("index", added=submission["id"]))


@app.get("/accessibility")
def accessibility_statement():
    return render_template("accessibility.html")


def reset_store() -> None:
    """Test hook: clear all submissions."""
    store.clear()


if __name__ == "__main__":
    # Binding all interfaces is required inside Docker; the container network is the boundary.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5001")))  # nosec B104
