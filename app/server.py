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
POST /submit                      HTML form handler

Storage is pluggable (app/storage.py): in-memory by default, DynamoDB when
STORAGE_BACKEND=dynamodb.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, url_for

from app.similarity import similarity_band, similarity_score, word_count
from app.storage import build_store

API_KEY = os.environ.get("SUBMISSION_API_KEY", "qa-demo-key")
MIN_TEXT_LENGTH = 20
MAX_TEXT_LENGTH = 20_000

app = Flask(__name__)
store = build_store()
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


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "no-referrer"
    # Found by SecurityTest.errorsDoNotLeakInternals (DEF-104): the dev server advertised
    # "Werkzeug/x Python/y". Overriding here means no environment reveals its stack.
    response.headers["Server"] = "submission-service"
    return response


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.headers.get("X-API-Key") != API_KEY:
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
    elif len(title) > 200:
        errors["title"] = "title must be 200 characters or fewer"
    if not author:
        errors["author"] = "author is required"
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
    items = store.list()
    return jsonify({"items": items, "count": len(items)})


@app.post("/api/submissions")
@require_api_key
def create_submission():
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
    return render_template("index.html", **page_context(store.list()))


@app.post("/submit")
def submit_form():
    payload = {k: request.form.get(k, "") for k in ("title", "author", "text")}
    errors = validate(payload)
    if errors:
        return render_template("index.html", **page_context(store.list(), errors, payload)), 400
    store.put(build_submission(payload))
    return redirect(url_for("index"))


def reset_store() -> None:
    """Test hook: clear all submissions."""
    store.clear()


if __name__ == "__main__":
    # Binding all interfaces is required inside Docker; the container network is the boundary.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5001")))  # nosec B104
