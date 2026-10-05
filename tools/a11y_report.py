"""Accessibility audit report.

Scans every state of the page with axe-core, then runs scripted checks axe cannot do
(keyboard use, announcements of errors and results, zoom, text spacing, forced colours,
reduced motion), and writes:

    reports/accessibility.html   readable report, one section per page state
    reports/accessibility.json   full machine-readable results
    reports/accessibility.md     short summary for a pipeline run page

    python -m tools.a11y_report                 # scans a locally started app
    BASE_URL=https://... python -m tools.a11y_report

Exit code is non-zero when any WCAG A/AA violation is found, whatever its impact.

What this does NOT prove: automated rules cover only part of WCAG. See
docs/11_accessibility.md for the manual checks that conformance also needs.
"""
from __future__ import annotations

import html
import json
import os
import socket
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
CLEAN = {"title": "Photosynthesis in C4 plants", "author": "Ada Lovelace",
         "text": "C4 plants concentrate carbon dioxide around rubisco using a specialised leaf anatomy."}
COPIED = {"title": "Cell energy", "author": "Charles Babbage",
          "text": "The mitochondria is the powerhouse of the cell and produces energy through respiration"}


def _start_local_app() -> tuple[str, object]:
    import logging
    from werkzeug.serving import make_server
    from app import server as app_server

    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app_server.reset_store()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd = make_server("127.0.0.1", port, app_server.app, threaded=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}", httpd


def _submit(page, data: dict) -> None:
    page.get_by_label("Title").fill(data["title"])
    page.get_by_label("Author").fill(data["author"])
    page.get_by_label("Paper text").fill(data["text"])
    page.get_by_test_id("submit-button").click()


def _axe(page) -> dict:
    from axe_playwright_python.sync_playwright import Axe

    r = Axe().run(page, options={"runOnly": {"type": "tag", "values": WCAG_TAGS}}).response
    slim = lambda items: [
        {"id": v["id"], "impact": v.get("impact"), "help": v["help"], "helpUrl": v["helpUrl"],
         "tags": [t for t in v["tags"] if t.startswith("wcag")],
         "nodes": [{"html": n["html"][:200], "summary": (n.get("failureSummary") or "")[:300]} for n in v["nodes"]]}
        for v in items
    ]
    return {"violations": slim(r["violations"]), "incomplete": slim(r["incomplete"]),
            "passes": sorted(v["id"] for v in r["passes"]), "axe_version": r["testEngine"]["version"]}


def _keyboard_checks(page) -> list[dict]:
    """Things axe cannot test: real tab order, visible focus, and submitting by keyboard."""
    page.goto("/")
    order, focus_visible = [], True
    for _ in range(10):
        page.keyboard.press("Tab")
        info = page.evaluate(
            """() => { const e = document.activeElement; if (!e || e === document.body) return null;
                 const s = getComputedStyle(e);
                 return {id: e.id || e.getAttribute('data-testid') || e.getAttribute('role') || (e.tagName.toLowerCase() + ':' + e.textContent.trim().slice(0, 24)),
                         ring: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 || s.boxShadow !== 'none'}; }"""
        )
        if info is None or (order and info["id"] == order[0]):
            break
        order.append(info["id"])
        focus_visible = focus_visible and info["ring"]
    expected = ["title", "author", "text", "submit-button"]
    form_order = [i for i in order if i in expected]

    page.goto("/")
    page.get_by_label("Title").focus()
    page.keyboard.type("Keyboard only")
    page.keyboard.press("Tab"); page.keyboard.type("No mouse")
    page.keyboard.press("Tab"); page.keyboard.type("This submission was entered and sent using only the keyboard.")
    page.keyboard.press("Tab"); page.keyboard.press("Enter")
    row = page.get_by_test_id("submission-row").filter(has_text="Keyboard only")
    try:
        row.first.wait_for(timeout=5000)   # the form posts and redirects; wait for the result row
        submitted = True
    except Exception:
        submitted = False

    return [
        {"check": "Tab order follows the visual order of the form", "wcag": "2.4.3 Focus Order",
         "pass": form_order == expected, "detail": " > ".join(order)},
        {"check": "Every focused control shows a visible focus indicator", "wcag": "2.4.7 Focus Visible",
         "pass": focus_visible, "detail": "outline or focus ring detected on each stop"},
        {"check": "Form can be completed and submitted with the keyboard alone", "wcag": "2.1.1 Keyboard",
         "pass": submitted, "detail": "typed all fields, pressed Enter on the button"},
    ]


def _reflow_checks(browser, base_url: str) -> list[dict]:
    """WCAG 1.4.10: content reflows at 320 CSS px wide (equivalent to 400% zoom) without two-way scrolling."""
    ctx = browser.new_context(base_url=base_url, viewport={"width": 320, "height": 640})
    page = ctx.new_page(); page.goto("/")
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    small = page.evaluate(
        """() => [...document.querySelectorAll('button, input, textarea, a')].filter(e => {
             const r = e.getBoundingClientRect(); return r.width > 0 && (r.width < 24 || r.height < 24); }).map(e => e.outerHTML.slice(0, 80))"""
    )
    ctx.close()
    return [
        {"check": "No horizontal page scroll at 320 px wide", "wcag": "1.4.10 Reflow",
         "pass": overflow <= 0, "detail": f"overflow {overflow}px (the data table scrolls inside its own container, which the criterion permits)"},
        {"check": "Interactive targets are at least 24 by 24 px", "wcag": "2.5.8 Target Size (Minimum)",
         "pass": not small, "detail": "; ".join(small) or "all targets meet the minimum"},
    ]


TEXT_SPACING_CSS = "* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }"


def _wait_focused(page, selector: str) -> None:
    """The script that moves focus loads after the markup, so give it a moment. A real
    failure still shows up: the check that follows reads the focused element itself."""
    from playwright.sync_api import expect

    try:
        expect(page.locator(selector)).to_be_focused(timeout=3000)
    except AssertionError:
        pass


def _announcement_checks(page) -> list[dict]:
    """Outcome of a submission must reach assistive technology without the user hunting for it."""
    page.goto("/")
    page.keyboard.press("Tab")
    first = page.evaluate("document.activeElement.textContent.trim()")
    page.keyboard.press("Enter")
    skipped_to = page.evaluate("document.activeElement.id")

    page.goto("/")
    _submit(page, {"title": "", "author": "", "text": "short"})
    page.wait_for_selector("#error-summary")
    _wait_focused(page, "#error-summary")
    err = page.evaluate(
        """() => { const e = document.getElementById('error-summary');
             return {focused: document.activeElement === e, role: e.getAttribute('role'),
                     links: [...e.querySelectorAll('a')].map(a => a.getAttribute('href')),
                     invalid: [...document.querySelectorAll('[aria-invalid=true]')].map(i => i.id),
                     described: [...document.querySelectorAll('[aria-invalid=true]')].every(i =>
                        i.getAttribute('aria-describedby').split(' ').some(id => document.getElementById(id).textContent.trim())),
                     title: document.title}; }"""
    )
    page.goto("/")
    _submit(page, CLEAN)
    page.wait_for_selector("#status-message")
    _wait_focused(page, "#status-message")
    ok = page.evaluate(
        "() => { const e = document.getElementById('status-message'); return {focused: document.activeElement === e, role: e.getAttribute('role'), text: e.textContent.trim()}; }"
    )
    name = page.get_by_role("button", name="Check similarity").count()
    return [
        {"check": "First tab stop is a skip link that moves focus to the main content", "wcag": "2.4.1 Bypass Blocks",
         "pass": first == "Skip to main content" and skipped_to == "main", "detail": f"first stop: {first!r}; focus after activating: #{skipped_to}"},
        {"check": "Validation errors are summarised in an alert that receives focus", "wcag": "4.1.3 Status Messages, 3.3.1 Error Identification",
         "pass": err["focused"] and err["role"] == "alert" and err["links"] == ["#title", "#author", "#text"],
         "detail": f"role={err['role']}, focused={err['focused']}, links={err['links']}"},
        {"check": "Each invalid field is marked invalid and tied to its error text", "wcag": "3.3.1 Error Identification, 1.3.1 Info and Relationships",
         "pass": err["invalid"] == ["title", "author", "text"] and err["described"], "detail": f"aria-invalid on {err['invalid']}"},
        {"check": "Page title announces the error state", "wcag": "2.4.2 Page Titled",
         "pass": err["title"].startswith("Error:"), "detail": err["title"]},
        {"check": "A successful submission is confirmed in a status message that receives focus", "wcag": "4.1.3 Status Messages",
         "pass": ok["focused"] and ok["role"] == "status" and "Submission added" in ok["text"], "detail": ok["text"][:90]},
        {"check": "The button's accessible name matches its visible label", "wcag": "2.5.3 Label in Name",
         "pass": name == 1, "detail": "button exposed as 'Check similarity'"},
    ]


def _adaptation_checks(browser, base_url: str) -> list[dict]:
    """User-chosen display settings: text spacing, zoom, forced colours, reduced motion."""
    out = []
    overflow_js = "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    clipped_js = """() => [...document.querySelectorAll('h1,h2,p,label,button,th,td,li,span,a')].filter(e => {
        const s = getComputedStyle(e); return e.textContent.trim() && s.overflow !== 'visible' && s.overflowX !== 'auto'
          && (e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1); }).map(e => e.outerHTML.slice(0, 60))"""

    # bypass_csp lets the test inject the spacing rules the way a user style sheet or browser
    # extension would; those are not subject to the page's Content Security Policy either.
    ctx = browser.new_context(base_url=base_url, viewport={"width": 1280, "height": 800}, bypass_csp=True)
    page = ctx.new_page(); page.goto("/"); _submit(page, COPIED); page.wait_for_selector("#status-message"); page.wait_for_load_state("load")
    page.add_style_tag(content=TEXT_SPACING_CSS)
    clipped = page.evaluate(clipped_js); overflow = page.evaluate(overflow_js)
    out.append({"check": "Increased text spacing causes no clipped or overlapping text", "wcag": "1.4.12 Text Spacing",
                "pass": not clipped and overflow <= 0, "detail": "; ".join(clipped) or "no clipped text, no page overflow"})
    ctx.close()

    # 200% zoom on a 1280 px window is the same layout as a 640 px viewport.
    ctx = browser.new_context(base_url=base_url, viewport={"width": 640, "height": 400})
    page = ctx.new_page(); page.goto("/"); _submit(page, COPIED); page.wait_for_selector("#status-message"); page.wait_for_load_state("load")
    overflow = page.evaluate(overflow_js)
    visible = page.get_by_test_id("submit-button").is_visible() and page.get_by_label("Paper text").is_visible()
    out.append({"check": "At 200% zoom all content and controls remain available without sideways page scrolling", "wcag": "1.4.4 Resize Text",
                "pass": overflow <= 0 and visible, "detail": f"page overflow {overflow}px at the 200% layout"})
    ctx.close()

    ctx = browser.new_context(base_url=base_url, forced_colors="active")
    page = ctx.new_page(); page.goto("/"); _submit(page, COPIED); page.wait_for_selector("#status-message"); page.wait_for_load_state("load")
    borders = page.evaluate(
        """() => ['.btn', '#title', '.pill', '.card'].map(sel => { const s = getComputedStyle(document.querySelector(sel));
             return [sel, s.borderTopStyle !== 'none' && parseFloat(s.borderTopWidth) > 0]; })"""
    )
    missing = [sel for sel, has in borders if not has]
    out.append({"check": "In forced-colours (high contrast) mode, controls and status badges keep a visible boundary", "wcag": "1.4.11 Non-text Contrast",
                "pass": not missing, "detail": "missing border on " + ", ".join(missing) if missing else "button, input, status pill and cards all have borders"})
    forced_axe = _axe(page)
    ctx.close()

    ctx = browser.new_context(base_url=base_url, reduced_motion="reduce")
    page = ctx.new_page(); page.goto("/")
    dur = page.evaluate("getComputedStyle(document.querySelector('.btn')).transitionDuration")
    out.append({"check": "Animations and transitions are switched off when the user asks for reduced motion", "wcag": "2.3.3 Animation from Interactions",
                "pass": all(float(d.strip().rstrip('s')) == 0 for d in dur.split(',')), "detail": f"button transition-duration: {dur}"})
    ctx.close()
    return out, forced_axe


def audit(base_url: str) -> dict:
    from playwright.sync_api import sync_playwright

    states = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(base_url=base_url)
        page = ctx.new_page()

        page.goto("/")
        states.append({"name": "Initial page", **_axe(page)})

        _submit(page, CLEAN); _submit(page, COPIED)
        states.append({"name": "With results and a success message", **_axe(page)})

        _submit(page, {"title": "", "author": "", "text": "short"})
        states.append({"name": "Validation errors shown", **_axe(page)})

        manual_auto = _keyboard_checks(page)
        manual_auto += _announcement_checks(page)

        page.goto("/accessibility")
        states.append({"name": "Accessibility statement page", **_axe(page)})
        ctx.close()

        mctx = browser.new_context(base_url=base_url, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        mpage = mctx.new_page(); mpage.goto("/")
        states.append({"name": "Phone viewport (390 px)", **_axe(mpage)})
        mctx.close()

        manual_auto += _reflow_checks(browser, base_url)
        adaptation, forced_axe = _adaptation_checks(browser, base_url)
        manual_auto += adaptation
        states.append({"name": "Forced-colours (high contrast) mode", **forced_axe})
        browser.close()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": base_url, "standard": "WCAG 2.2 level A and AA (axe-core rules)",
        "axe_version": states[0]["axe_version"], "states": states, "scripted_checks": manual_auto,
    }


def summarise(result: dict) -> dict:
    v = [x for s in result["states"] for x in s["violations"]]
    return {
        "violations": len(v),
        "by_impact": {k: sum(1 for x in v if x["impact"] == k) for k in ("critical", "serious", "moderate", "minor")},
        "needs_review": len({x["id"] for s in result["states"] for x in s["incomplete"]}),
        "rules_passed": len({r for s in result["states"] for r in s["passes"]}),
        "scripted_failed": sum(1 for c in result["scripted_checks"] if not c["pass"]),
    }


def to_markdown(result: dict) -> str:
    s = summarise(result)
    lines = ["### Accessibility audit", "", f"Standard: {result['standard']}, axe-core {result['axe_version']}.", "",
             "| Measure | Result |", "|---|---:|",
             f"| WCAG rule violations | {s['violations']} |", f"| Distinct rules passed | {s['rules_passed']} |",
             f"| Rules needing human review | {s['needs_review']} |",
             f"| Scripted checks failed | {s['scripted_failed']} of {len(result['scripted_checks'])} |", "",
             "Automated checks cover only part of WCAG. This is not a conformance claim."]
    return "\n".join(lines) + "\n"


def to_html(result: dict) -> str:
    s = summarise(result)
    e = html.escape
    def issues(items, kind):
        if not items:
            return f"<p class='ok'>No {kind}.</p>"
        out = []
        for v in items:
            nodes = "".join(f"<li><code>{e(n['html'])}</code><br><span class='muted'>{e(n['summary'])}</span></li>" for n in v["nodes"])
            out.append(f"<div class='issue'><strong>{e(v['id'])}</strong> <span class='tag'>{e(str(v['impact']))}</span> "
                       f"<span class='muted'>{e(' '.join(v['tags']))}</span><p>{e(v['help'])} "
                       f"<a href='{e(v['helpUrl'])}'>Rule details</a></p><ul>{nodes}</ul></div>")
        return "".join(out)
    sections = "".join(
        f"<section><h2>{e(st['name'])}</h2><p class='muted'>{len(st['passes'])} rules passed</p>"
        f"<h3>Violations</h3>{issues(st['violations'], 'violations')}"
        f"<h3>Needs human review</h3>{issues(st['incomplete'], 'items needing review')}</section>"
        for st in result["states"])
    rows = "".join(f"<tr><td class='{'ok' if c['pass'] else 'bad'}'>{'Pass' if c['pass'] else 'Fail'}</td><td>{e(c['check'])}</td>"
                   f"<td>{e(c['wcag'])}</td><td class='muted'>{e(c['detail'])}</td></tr>" for c in result["scripted_checks"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Accessibility audit report</title><style>
body{{font-family:system-ui,sans-serif;max-width:60rem;margin:0 auto;padding:1.5rem;color:#1c2430;line-height:1.5}}
h1{{margin-bottom:.2rem}} .muted{{color:#5b6676;font-size:.9rem}} .ok{{color:#1f7a3a;font-weight:600}} .bad{{color:#a30d2d;font-weight:600}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));gap:.75rem;margin:1rem 0}}
.card{{border:1px solid #e2e6ec;border-radius:8px;padding:.9rem}} .card b{{display:block;font-size:1.7rem}}
section{{border-top:1px solid #e2e6ec;margin-top:1.5rem;padding-top:.5rem}} .issue{{border-left:4px solid #a30d2d;padding:.2rem .8rem;margin:.6rem 0;background:#fafbfc}}
.tag{{background:#eef1f5;border-radius:999px;padding:.1rem .5rem;font-size:.8rem}} code{{font-size:.85rem;word-break:break-all}}
table{{border-collapse:collapse;width:100%}} td,th{{text-align:left;padding:.5rem;border-bottom:1px solid #e2e6ec;vertical-align:top}}
.note{{background:#fff8e1;border:1px solid #f0d98a;border-radius:8px;padding:.8rem 1rem;margin:1rem 0}}
</style></head><body><main>
<h1>Accessibility audit report</h1>
<p class="muted">Target {e(result['target'])} · {e(result['generated_at'])} · {e(result['standard'])} · axe-core {e(result['axe_version'])}</p>
<div class="cards">
<div class="card"><b>{s['violations']}</b>WCAG rule violations</div>
<div class="card"><b>{s['rules_passed']}</b>distinct rules passed</div>
<div class="card"><b>{s['needs_review']}</b>rules needing human review</div>
<div class="card"><b>{len(result['scripted_checks']) - s['scripted_failed']}/{len(result['scripted_checks'])}</b>scripted checks passed</div>
</div>
<div class="note"><strong>Scope of this report.</strong> Automated rules can confirm only part of WCAG. A clean result here is
necessary for conformance but not sufficient. Screen reader behaviour, meaningful labels, error wording and
content clarity need the manual checks listed in <code>docs/11_accessibility.md</code>.</div>
<section><h2>Scripted checks beyond axe: keyboard, announcements, display settings</h2><table><thead><tr><th scope="col">Result</th><th scope="col">Check</th><th scope="col">WCAG criterion</th><th scope="col">Detail</th></tr></thead><tbody>{rows}</tbody></table></section>
{sections}
</main></body></html>"""


def main() -> int:
    base_url, httpd = os.environ.get("BASE_URL"), None
    if not base_url:
        base_url, httpd = _start_local_app()
    try:
        result = audit(base_url.rstrip("/"))
    finally:
        if httpd:
            httpd.shutdown()
    out = ROOT / "reports"; out.mkdir(exist_ok=True)
    (out / "accessibility.json").write_text(json.dumps(result, indent=2))
    (out / "accessibility.html").write_text(to_html(result))
    md = to_markdown(result); (out / "accessibility.md").write_text(md)
    print(md)
    s = summarise(result)
    return 1 if s["violations"] or s["scripted_failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
