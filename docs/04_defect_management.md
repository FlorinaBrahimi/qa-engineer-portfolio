# Defect Management

## Lifecycle

```
New -> Triaged -> In progress -> Ready for verification -> Verified -> Closed
                      \-> Won't fix / Duplicate / Cannot reproduce (with reason)
```

Triage happens daily, 10 minutes, with QE, dev lead and PM. QE proposes severity; the group sets priority.

## Severity vs priority

| Severity | Definition | Example |
|---|---|---|
| S1 Critical | Data loss, security breach, no workaround, blocks release | Submissions silently dropped under load |
| S2 Major | Core flow broken for many users, workaround is painful | Flagged status wrong for texts with Unicode quotes |
| S3 Minor | Non-core feature wrong, workaround exists | Error message typo |
| S4 Trivial | Cosmetic | Table misaligned by 2px |

Priority (P1 fix now, P2 this sprint, P3 backlog) is a business decision and can differ from severity.

## Report template

```
Title:        <component>: <one-line symptom>
Environment:  <in-process | docker | staging>, build <sha>, browser/OS if UI
Severity:     S1-S4         Priority: P1-P3
Found by:     <test id or exploratory charter>
Preconditions:
Steps to reproduce:
  1.
  2.
Expected:
Actual:
Evidence:     logs / screenshot / HAR / failing test name
Workaround:
Notes:        suspected cause, related tickets
```

## Sample defects from this project

### DEF-101 (S2 / P1) API: concurrent POSTs occasionally return duplicate ids

- **Environment:** in-process, commit before `_lock` was introduced in `app/server.py`
- **Found by:** TC-SCALE-001
- **Steps:** run `pytest -m scale` five times.
- **Expected:** 100 unique ids each run. **Actual:** 1 run in 5 produced 99 unique ids.
- **Evidence:** failing assertion `duplicate IDs under concurrency`, CI build 118.
- **Resolution:** store writes wrapped in a lock; regression test retained. Verified in build 121, closed.

### DEF-102 (S3 / P2) UI: validation error for `text` is not announced to screen readers

- **Environment:** docker, Chrome 129 + VoiceOver
- **Found by:** EXP-002 exploratory session
- **Steps:** submit the form with 5-character text using keyboard only.
- **Expected:** error is read out when focus returns to the field. **Actual:** silent.
- **Resolution:** `aria-describedby` added linking each input to its error span; TC-A11Y-002 extended. Verified, closed.

### DEF-104 (S3 / P2) API: responses advertise server stack in the `Server` header

- **Environment:** in-process and Docker (Werkzeug dev server); not reproducible on Lambda
- **Found by:** `SecurityTest.errorsDoNotLeakInternals` (Java suite), first run after adding leakage checks
- **Steps:** `curl -I http://localhost:5001/health`
- **Expected:** no technology disclosure. **Actual:** `Server: Werkzeug/3.1 Python/3.12`
- **Resolution:** `Server` header overridden in the app's `after_request` hook so every environment behaves the same. Verified by the Java and Python security suites, closed.

### DEF-115 (S2 / P1) API: over-long object id returns HTTP 500 on AWS

- **Environment:** live AWS only. Local runs passed.
- **Found by:** `test_hostile_object_ids_return_404_not_an_error` in the post-deploy pipeline
- **Steps:** GET `/api/submissions/` followed by 5,000 characters.
- **Expected:** 404. **Actual:** 500. DynamoDB rejects keys over 2,048 bytes; the in-memory store used locally has no such limit.
- **Resolution:** ids are validated as UUIDs before any storage call, so a malformed id cannot reach the database. A unit test asserts storage is never called. Verified locally and live, closed.
- **Lesson:** the third defect in this project that only appeared against the real cloud backend, which is the argument for running the suite post-deploy.

### DEF-109 (S2 / P1) API: author field has no maximum length

- **Found by:** security review against OWASP API4:2023 (Unrestricted Resource Consumption)
- **Steps:** POST a submission whose `author` is 100,000 characters.
- **Expected:** 400. **Actual:** 201, and the value was stored and returned in every list response.
- **Resolution:** 200-character maximum, matching `title`. `test_api4_every_text_field_has_an_enforced_maximum` covers all three text fields. Verified, closed.

### DEF-110 (S3 / P2) API: oversized request bodies are read in full

- **Found by:** security review, API4:2023
- **Steps:** POST a 3 MB JSON body.
- **Expected:** refused before processing. **Actual:** the whole body was parsed before validation rejected it.
- **Resolution:** 256 KB request cap, answered with 413 `payload_too_large`. Verified, closed.

### DEF-111 (S3 / P2) API: unknown routes and wrong methods return HTML framework pages

- **Found by:** security review, API8:2023 (Security Misconfiguration)
- **Expected:** JSON errors with no framework fingerprint. **Actual:** Werkzeug's HTML 404 and 405 pages.
- **Resolution:** JSON error handlers for API paths, plus a generic 500 handler that logs detail server-side only. Verified, closed.

### DEF-112 (S3 / P2) Several recommended security headers missing; CSP too loose

- **Found by:** comparison with the OWASP Secure Headers Project
- **Actual:** no HSTS, Permissions-Policy, Cross-Origin-Opener-Policy, Cross-Origin-Resource-Policy or Cache-Control; CSP was only `default-src 'self'`.
- **Resolution:** all added; CSP now also sets `object-src`, `base-uri`, `form-action` and `frame-ancestors`. Asserted on seven kinds of response, including errors. Verified, closed.

### DEF-113 (S3 / P2) Reopened DEF-104: development server still sent its own Server header

- **Found by:** raw header inspection during the security review
- **Actual:** two `Server` headers were sent locally, `Werkzeug/3.1.9 Python/3.12.5` and the override. The earlier test read only one of them.
- **Resolution:** the server's version string is replaced at source, and the test now inspects every header on four paths. Verified, closed.

### DEF-114 (S3 / P2) API key compared with a non-constant-time operator

- **Found by:** code review against ASVS V2 (CWE-208, observable timing discrepancy)
- **Resolution:** `hmac.compare_digest`. A test guards against regression. Verified, closed.

### DEF-108 (S4 / P3) UI: footer link target is smaller than 24 px

- **Found by:** the audit's target-size check, minutes after the accessibility statement link was added
- **Expected:** stand-alone links are at least 24 by 24 px (WCAG 2.5.8). **Actual:** the footer link was about 17 px high.
- **Resolution:** stand-alone links given a 24 px minimum height. Caught and fixed before release. Verified, closed.

### DEF-107 (S3 / P2) UI: results table cannot be scrolled by keyboard on narrow screens

- **Environment:** all, at viewport widths below 820 px
- **Found by:** the accessibility audit (`tools/a11y_report.py`), axe rule `scrollable-region-focusable`. The existing desktop-only scan could not see it.
- **Expected:** a region that scrolls sideways can be focused and scrolled with the keyboard (WCAG 2.1.1). **Actual:** keyboard users could not reach the Similarity and Status columns on a phone-width layout.
- **Resolution:** the table container is now focusable with a visible focus ring and its own region label. A first attempt gave it the same name as the surrounding section, which a new landmark-uniqueness test caught before release. Phone-viewport and keyboard-only tests added. Verified, closed.

### DEF-106 (S2 / P1) API: wrongly typed field crashes with HTTP 500

- **Environment:** all
- **Found by:** `test_wrongly_typed_field_is_rejected_naming_field`, written by the AI test generator and absent from both hand-written suites
- **Steps:** POST `/api/submissions` with `"title": 123`, `"author": {}` or `"text": []`.
- **Expected:** 400 naming the field. **Actual:** 500, unhandled `AttributeError` on `.strip()`.
- **Resolution:** validation now rejects non-string values with `<field> must be a string`. The generated tests were reviewed and promoted into `tests/api/test_generated_api.py`. Verified locally and live, closed.

### DEF-105 (S3 / P2) UI: "flagged" status pill fails WCAG AA colour contrast

- **Environment:** live AWS stack only at first; local and CI runs passed
- **Found by:** `test_axe_core_reports_no_serious_violations` run against the deployed URL
- **Expected:** contrast of at least 4.5:1. **Actual:** 4.13:1 (`#e4123f` on `#fdecef`).
- **Root cause of the escape:** the scan ran on an empty table locally, so the pill was never rendered. The live table had data.
- **Resolution:** pill text darkened to `#a30d2d` (7.0:1). The test now seeds a clear and a flagged row before scanning, so the gap is closed in every environment. Verified locally and live, closed.

### DEF-103 (S4 / P3) UI: status cell colour alone distinguishes flagged from clear

- **Found by:** axe review (colour is not the only cue once text is present, so downgraded to S4).
- **Status:** Won't fix for v1.1; the status word is present as text, which satisfies WCAG 1.4.1. Logged for design review.
