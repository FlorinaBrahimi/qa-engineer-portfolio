# Quality Risk Register: Submission Service v1.1

Scored in refinement. Likelihood and impact 1-5; score = L × I. Reviewed at each stand-up for anything ≥ 12.

| ID | Risk | L | I | Score | Early signal | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| R1 | Similarity threshold (25%) misclassifies borderline papers | 3 | 5 | 15 | Fixture scores drift after scorer change | Fixtures with exact expected scores (TC-API-003..005); exploratory charter EXP-001 | QE | Open |
| R2 | Race conditions lose or duplicate submissions under load | 3 | 5 | 15 | Non-deterministic failures in scale suite | TC-SCALE-001 in every PR; lock around store; JMeter nightly | Dev + QE | Mitigated (DEF-101) |
| R3 | Staging S3 bucket not provisioned in time for integration test | 4 | 3 | 12 | Platform ticket still open day 5 | moto-backed tests give coverage without the bucket; escalate day 6 | QE | Open |
| R4 | Auth bypass via missing decorator on a new endpoint | 2 | 5 | 10 | New route added without test | Parametrised TC-SEC-001 enumerates every route; PR checklist item | Dev | Mitigated |
| R5 | UI selectors change and break Playwright suite | 4 | 2 | 8 | Locator timeouts in CI | `data-testid` convention agreed with front-end; Page Object isolates selectors | QE | Mitigated |
| R6 | Flaky tests erode trust in the pipeline | 3 | 3 | 9 | Flakiness score > 30% in `predict_flaky.py` | Quarantine marker, weekly flaky review, retries not allowed to hide failures | QE | Monitoring |
| R7 | Lambda silently skips malformed archives | 2 | 3 | 6 | `rejected` count rising in CloudWatch | TC-AWS-003; alarm on rejected metric | Dev | Mitigated |
| R8 | Accessibility regressions from new table styling | 2 | 4 | 8 | axe violations in PR | TC-A11Y suite blocks merge on serious/critical | QE | Mitigated |

**Dependencies**
- Platform team: staging IAM role (R3).
- Front-end team: keep `data-testid` attributes stable (R5).
- Jenkins agent with JMeter installed for nightly performance stage.
