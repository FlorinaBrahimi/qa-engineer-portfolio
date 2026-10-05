# Test Strategy: Submission Service

**Owner:** Quality Engineering · **Scope:** Submission Service (API + web UI + S3 archive + Lambda) · **Status:** Living document, reviewed each PI

## 1. Objectives

1. Every change ships with evidence that functional behaviour, security posture and performance budgets still hold.
2. Feedback to developers arrives in minutes (smoke on commit), not days.
3. Quality risks are visible in the sprint, with an owner and a mitigation, before code is written.

## 2. Test levels and ownership

| Level | What it proves | Owner | Tooling | Runs |
|---|---|---|---|---|
| Unit | Scoring logic, validation, Lambda handler | Developers (QE reviews) | pytest | every commit |
| API / contract | Endpoint behaviour matches OpenAPI | QE | pytest + requests, REST Assured (Java) | every commit |
| UI | Critical user journeys work in a real browser | QE | Playwright, Page Objects | every PR |
| Integration | UI, API and AWS pieces agree with each other | QE | pytest + moto | every PR |
| Security | Auth, hardening headers, injection handling | QE + security champion | pytest, OWASP ZAP (baseline scan, nightly) | every PR / nightly |
| Accessibility | WCAG 2.1 AA on user-facing pages | QE | axe-core via Playwright | every PR |
| Scale / performance | Latency and error budgets under load | QE + platform | in-process concurrency tests, JMeter | every PR (light) / nightly (full) |
| Mobile | Responsive layout, touch flows | QE | Playwright device emulation, Appium on device farm | every PR / weekly |
| Exploratory / manual | Usability, edge cases automation can't predict | Whole scrum team | Session-based charters | each sprint |

## 3. Automation pyramid and entry criteria

Target split of automated checks: ~60% unit/API, ~30% integration, ~10% UI. A UI test is only added when the behaviour cannot be verified below the UI.

A test is merged only if it:
- is independent (creates its own data via `SubmissionFactory`, cleans up after itself);
- runs green three times in a row locally and in CI;
- has a stable, test-id based locator strategy (no XPath on layout);
- maps back to a test case ID or a user story.

## 4. Environments

| Environment | Purpose | Data | Target |
|---|---|---|---|
| In-process | Fast feedback, developer laptops, PR checks | Factory generated | default |
| Docker compose | Same as PR but containerised, mirrors CI image | Factory generated | `BASE_URL=http://sut:5001` |
| Staging | Nightly full regression, JMeter, ZAP | Masked production-shaped snapshot | `BASE_URL=https://staging...` |
| Production | Post-deploy smoke only, read-only | Live | `pytest -m smoke` |

The same test code targets every environment via `BASE_URL`; nothing is environment-specific inside a test.

## 5. Risk-based prioritisation

Each story is scored for likelihood × impact in refinement (see `05_risk_register.md`). High-risk areas (scoring accuracy, auth, data loss) get: automated coverage at two levels, an exploratory charter, and a review by a second QE.

## 6. Defect management

Defects follow the lifecycle in `04_defect_management.md`: New → Triaged → In progress → Ready for verification → Verified → Closed. Severity and priority are set at triage, not by the reporter alone.

## 7. Metrics reviewed each sprint

- Escaped defects (found in production) per release, target 0 Sev-1/Sev-2.
- Automation pass rate and flakiness trend (`ai_testing/predict_flaky.py`).
- Mean time from PR open to first test signal, target < 10 min.
- Coverage of acceptance criteria by automated tests, target 100% for P1 stories.

## 8. AI-assisted practices

AI tools are used to generate candidate tests, rank flaky tests and draft defect reports. Every AI output is reviewed by a human before it enters the suite or the tracker. See `07_ai_in_qa_evaluation.md`.
