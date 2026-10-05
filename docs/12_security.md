# Security testing: standards, coverage and limits

## Standards used

| Standard | Why it fits | How it is used here |
|---|---|---|
| OWASP API Security Top 10 (2023) | The service is an API first | Primary checklist; one test section per risk |
| OWASP Application Security Verification Standard (ASVS) 4.0, Level 1 | The recognised requirements list for web application controls | Chapters V2, V4, V5, V7, V9, V13, V14 selected as relevant |
| OWASP Secure Headers Project | Defines the response headers a browser-facing app should send | Asserted on every kind of response |
| OWASP Web Security Testing Guide (WSTG) | The testing method behind the cases | Input, error-handling and configuration test techniques |
| OWASP Top 10 (2021 categories) | The common language for web risk | Cross-reference in the table below |
| CWE | Precise weakness identifiers | Cited in tests and defects |

## Layers of testing

| Layer | Industry term | Tool | Runs |
|---|---|---|---|
| Behavioural security tests | Security regression tests | pytest (`tests/security/`), REST Assured (`SecurityTest.java`) | every build, and against live AWS after deploy |
| Dynamic scan of the running app | DAST | OWASP ZAP baseline | every build (GitHub Actions) |
| Code analysis | SAST | bandit | every build |
| Dependency vulnerabilities | SCA | pip-audit | every build |
| Secrets in the repository | Secret scanning | gitleaks, full history | every build |
| Infrastructure templates | IaC scanning | cfn-lint | every build |
| Deployed cloud configuration | Cloud posture checks | AWS SDK tests (`AwsDeploymentTest.java`) | after every deploy |
| Transport | TLS checks | pytest (`test_transport_live.py`) | against live AWS |

Run the local layers with `make audit` and `pytest -m security`.

## OWASP API Security Top 10 (2023) traceability

| Risk | Status | Evidence |
|---|---|---|
| API1 Broken Object Level Authorization | Not applicable by design, residual check in place | Single tenant: one key, no per-user objects. `test_api1_object_ids_are_random_uuids_not_sequential` confirms ids cannot be enumerated |
| API2 Broken Authentication | Tested | Missing, wrong, near-miss and malformed keys on every endpoint; key refused in the URL; no oracle between missing and wrong; constant-time comparison; default key fails closed on AWS |
| API3 Broken Object Property Level Authorization | Tested | Mass assignment ignored; responses expose only documented properties and never the paper text |
| API4 Unrestricted Resource Consumption | Tested, with a known gap | 256 KB body cap (413); maximum on every text field; bounded list with validated `limit`. **Gap: no rate limiting**, see accepted risks |
| API5 Broken Function Level Authorization | Not applicable by design, residual check in place | One role. Fifteen admin, debug and framework paths confirmed absent |
| API6 Unrestricted Access to Sensitive Business Flows | Not applicable | No purchase, booking or other flow that automation could abuse for gain |
| API7 Server Side Request Forgery | Not applicable | The service never fetches a URL supplied by a client |
| API8 Security Misconfiguration | Tested | Secure headers on every response; JSON errors; unsupported methods refused; no CORS; no directory listing; no technology disclosure; internal errors reveal nothing; ZAP baseline |
| API9 Improper Inventory Management | Tested | Published OpenAPI paths must equal the routes that exist; no versioned or shadow endpoints |
| API10 Unsafe Consumption of APIs | Not applicable | The service calls no third-party API. AWS SDK calls go to DynamoDB only |

## OWASP Top 10 (2021) cross-reference

| Category | Covered by |
|---|---|
| A01 Broken Access Control | API1, API3, API5 tests; CSRF tests |
| A02 Cryptographic Failures | TLS 1.2+ only, obsolete versions refused, HSTS; DynamoDB encryption at rest |
| A03 Injection | Fifteen hostile payload classes stored inertly; stored and reflected XSS; CSP blocks inline script; JSON type and media-type enforcement |
| A04 Insecure Design | Fail-closed default key; server-owned properties; body and field limits |
| A05 Security Misconfiguration | API8 tests; ZAP; cfn-lint; AWS posture tests |
| A06 Vulnerable and Outdated Components | pip-audit on every build |
| A07 Identification and Authentication Failures | API2 tests |
| A08 Software and Data Integrity Failures | GitHub deploys via short-lived OIDC role, no stored cloud keys; gitleaks. **Gap: dependencies are not pinned to hashes** |
| A09 Security Logging and Monitoring Failures | Failed authentication and blocked cross-site posts are logged with context; keys and submission content never logged; CloudWatch error alarm verified |
| A10 Server-Side Request Forgery | Not applicable, as API7 |

## ASVS Level 1 areas exercised

| Chapter | Examples verified |
|---|---|
| V2 Authentication | Credential never in URL; constant-time comparison; no default credential in production |
| V4 Access Control | Deny by default on every API route; CSRF defence on the form (4.2.2) |
| V5 Validation, Sanitization, Encoding | Positive validation of type and length; output encoding in three render contexts; template injection inert |
| V7 Error Handling and Logging | Generic errors; no secrets or personal content in logs; security events logged |
| V9 Communications | TLS 1.2 or newer with a valid certificate; no plain HTTP |
| V13 API and Web Service | JSON only (415 otherwise); method allow-list; schema-conformant responses |
| V14 Configuration | Security headers; no debug features; no technology disclosure; dependency and secret scanning |

## Accepted risks and known gaps

These are real and are stated, not hidden.

| Gap | Why it exists | What would close it |
|---|---|---|
| No rate limiting or lockout on the API key | A Lambda Function URL has none built in; this account's concurrency quota is too low to reserve a cap | API Gateway usage plans or AWS WAF rate rules in front of the function |
| Web form is public and unauthenticated | It is a demo with no user accounts | A login, or removing the form from the public deployment |
| Single shared API key, no rotation schedule | Demo scope | Per-client keys in AWS Secrets Manager with rotation |
| Function URL is `AuthType: NONE` | Needed for a browser-reachable demo | CloudFront with Origin Access Control and IAM auth on the URL |
| Dependencies use minimum versions, not pinned hashes | Keeps the demo easy to install | `pip-compile --generate-hashes` and `pip install --require-hashes` |
| ZAP runs the passive baseline only | An active scan attacks the target and is slow | Scheduled ZAP full or API scan against a disposable environment |

## What this is not

This is a security regression suite aligned to recognised standards. It is not a penetration
test, a threat model review, or a compliance certification such as ISO 27001, SOC 2 or
Cyber Essentials. Those need independent, qualified assessors.
