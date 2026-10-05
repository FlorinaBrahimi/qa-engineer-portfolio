# Test Plan: Sprint 42, Submission Service v1.1

**Release:** v1.1 (adds similarity status + S3 archiving) · **Sprint:** 42 (2026-10-06 to 2026-10-17) · **QE:** Florina Brahimi · **Dev lead:** TBD · **PM:** TBD

## 1. Scope

**In scope**
- POST/GET/DELETE `/api/submissions` including validation and auth.
- Web form submission and results table.
- `status` field (`clear` / `flagged`) derived from the 25% threshold.
- Archiving to S3 and the CloudWatch metric Lambda.

**Out of scope**
- Billing and institution management (owned by another team).
- Browser support beyond latest Chrome, Firefox, Safari and iOS Safari.

## 2. Features to be tested and approach

| Feature | Approach | Automated? | Test case IDs |
|---|---|---|---|
| Create submission | API boundary + equivalence partitioning | Yes | TC-API-001..006, TC-API-012 |
| Read / list / delete | API state transitions | Yes | TC-API-007..010 |
| Validation | Negative tests, field-level messages | Yes | TC-API-011, TC-UI-004, TC-UI-005 |
| Auth | Missing / wrong key on each endpoint | Yes | TC-SEC-001..002 |
| UI journeys | Playwright, Page Object | Yes | TC-UI-001..003 |
| Similarity status | Fixtures with known scores | Yes | TC-API-003..005 |
| S3 archive + Lambda | moto-backed integration | Yes | TC-AWS-001..003 |
| Concurrency | 25 parallel users, 100 requests | Yes | TC-SCALE-001..002 |
| Accessibility | axe-core + structural checks | Yes | TC-A11Y-001..004 |
| Mobile | Device emulation; Appium on real device weekly | Partly | TC-MOB-001..003 |
| Exploratory | 2 × 60 min charters: "break the similarity score", "abuse the form" | No | EXP-001, EXP-002 |

## 3. Entry and exit criteria

**Entry:** story acceptance criteria agreed; feature branch deploys to in-process/Docker; test data factories updated.

**Exit:**
- 100% of P1 test cases executed, 0 open Sev-1/Sev-2 defects.
- Automated regression green on main for 2 consecutive runs.
- p95 latency for POST < 500 ms at 50 virtual users (JMeter nightly).
- No serious/critical axe violations.
- Exploratory charters completed and debriefed.

## 4. Schedule

| Day | Activity |
|---|---|
| 1-2 | Refinement, risk scoring, write test cases for new stories |
| 3-7 | Automate alongside development, in-process testing in PRs |
| 8 | Full regression on staging, JMeter run, ZAP baseline |
| 9 | Exploratory sessions, defect verification |
| 10 | Release readiness review, sign-off |

## 5. Resources and estimates

| Work item | Estimate (points) | Notes |
|---|---|---|
| API tests for status field | 2 | Extends existing suite |
| UI flagged/clear tests | 3 | New Page Object methods |
| S3/Lambda integration | 3 | moto setup reusable |
| JMeter plan + nightly job | 5 | New; needs Jenkins agent with JMeter |
| Exploratory charters | 2 | Pairing with developer |

## 6. Risks and dependencies

See `05_risk_register.md`. Key dependency: staging S3 bucket IAM role must be provisioned by platform team by day 6.

## 7. Deliverables

Automated suites in this repo, JUnit/HTML reports from CI, JMeter dashboard, defect log, sign-off note in the release ticket.
