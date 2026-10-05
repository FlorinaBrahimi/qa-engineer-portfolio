# QA Engineering Portfolio: Submission Service

A self-contained project that demonstrates every requirement of a Software Quality Engineer role:
test strategy and planning, automated and manual testing across UI, API, integration, scale,
security, accessibility, mobile and AWS, CI/CD/CT pipelines, defect and risk management, Agile
practice, and AI-assisted testing.

The system under test is a small Flask "Submission Service" (`app/`) that accepts papers and
returns a similarity score, so every test here actually runs.

## Quick start

```bash
make install          # pip deps + Chromium for Playwright
make test             # all Python suites, JUnit + HTML reports in reports/
make app              # run the service on :5001 (for Java / JMeter / manual testing)
make java             # REST Assured suite (needs the app running)
make java-aws         # same suite against live AWS, plus DynamoDB/Lambda/CloudWatch checks
make flaky            # predictive flakiness report
make unit             # unit tests with coverage report
make audit            # pip-audit + bandit security scans
make deploy           # deploy to AWS (Lambda + DynamoDB), see infra/README.md
```

Run a slice: `pytest -m smoke`, `pytest -m "ui or a11y"`, `pytest -m api -n auto`.
Target a deployed environment: `BASE_URL=https://staging.example pytest -m smoke`.

## API key

`qa-demo-key` is the default for local, Docker and CI test runs only. The deployed AWS app uses
a random key held in the `SUBMISSION_API_KEY` GitHub secret and in the git-ignored `.env`, so
it never appears in this repository. Load `.env` before running anything against the live URL.

## Requirement to evidence map

| Role requirement | Where it is demonstrated |
|---|---|
| **Test strategy & planning** | [docs/01_test_strategy.md](docs/01_test_strategy.md), [docs/02_test_plan.md](docs/02_test_plan.md), [docs/03_test_cases.md](docs/03_test_cases.md) |
| **Functional, regression, integration, scale testing** | `tests/api/`, `tests/ui/` (markers `smoke`/`regression`), `tests/integration/`, `tests/scale/` |
| **UI web automation** | Playwright + Page Object pattern: [tests/ui/pages/submission_page.py](tests/ui/pages/submission_page.py), [tests/ui/test_submission_ui.py](tests/ui/test_submission_ui.py) |
| **API automation, Python** | [tests/api/test_submissions_api.py](tests/api/test_submissions_api.py) with `requests` + pytest |
| **API automation, Java / Maven** | [java-api-tests/](java-api-tests/): REST Assured + JUnit 5 framework with a base class, API client, data factory, JSON-schema contract checks and parameterised boundary tests. With `-Paws` it reads the live URL from CloudFormation and uses the AWS SDK to verify DynamoDB, Lambda and CloudWatch behind the API. 61 tests |
| **Manual testing** | Exploratory charters and manual cases in [docs/03_test_cases.md](docs/03_test_cases.md) |
| **Multiple platforms / environments** | `BASE_URL` switch in [tests/conftest.py](tests/conftest.py); in-process, Docker, staging in the strategy |
| **Defect management** | Lifecycle, severity model, template and worked examples in [docs/04_defect_management.md](docs/04_defect_management.md) |
| **Risk mitigation** | Scored register with owners and signals: [docs/05_risk_register.md](docs/05_risk_register.md) |
| **STLC / QA methodologies** | Entry/exit criteria, levels, pyramid, metrics across `docs/` |
| **CI/CD/CT: Jenkins** | [Jenkinsfile](Jenkinsfile): Docker-free declarative pipeline with parallel stages, JUnit publishing, security scans and a nightly JMeter stage. Setup: [docs/10_jenkins_setup.md](docs/10_jenkins_setup.md) |
| **CI/CD/CT: GitHub** | [.github/workflows/ci.yml](.github/workflows/ci.yml) tests every push; [.github/workflows/deploy.yml](.github/workflows/deploy.yml) then deploys to AWS and tests the live stack. Both proven on GitHub |
| **Docker** | [Dockerfile](Dockerfile), [docker-compose.yml](docker-compose.yml) (app + tests, healthcheck gated) |
| **Agile: Scrum & Kanban, estimation, test data** | [docs/06_agile_practices.md](docs/06_agile_practices.md), [testdata/factory.py](testdata/factory.py) |
| **AI-assisted test generation** | [ai_testing/generate_tests.py](ai_testing/generate_tests.py) (Claude via Anthropic SDK, grounded in the OpenAPI contract) |
| **Predictive analysis / smart automation** | [ai_testing/predict_flaky.py](ai_testing/predict_flaky.py) + its own tests; wired into both pipelines |
| **Evaluating modern QA tools** | [docs/07_ai_in_qa_evaluation.md](docs/07_ai_in_qa_evaluation.md) |
| **Mobile automation** | [tests/mobile/test_mobile.py](tests/mobile/test_mobile.py): device emulation always, Appium when a server is available |
| **Performance (JMeter)** | [performance/](performance/): plan, run script and thresholds. Runs in every pipeline build; results are converted to JUnit by [tools/jmeter_report.py](tools/jmeter_report.py) so they appear with the other test results, and a breached threshold blocks the deploy |
| **AWS (S3, Lambda, CloudWatch)** | [aws/](aws/) production code + [tests/aws/](tests/aws/) via moto; DynamoDB backend in [app/storage.py](app/storage.py) |
| **Live AWS deployment + CD** | [infra/](infra/) CloudFormation + deploy script, [.github/workflows/deploy.yml](.github/workflows/deploy.yml) deploys and tests the live URL. Runbook: [infra/README.md](infra/README.md) |
| **Security testing** | Behavioural tests in [tests/security/](tests/security/) and `SecurityTest.java`; dependency scan (pip-audit) and static analysis (bandit) via `make audit`. See [security/README.md](security/README.md) |
| **Accessibility testing** | Audit tool [tools/a11y_report.py](tools/a11y_report.py) produces an HTML report per run: axe-core WCAG 2.2 A/AA across six page states, plus fifteen scripted checks for keyboard use, announcements, zoom, text spacing, forced colours and reduced motion. The app publishes an accessibility statement. Tests in [tests/accessibility/](tests/accessibility/). Evidence, limits and legal position: [docs/11_accessibility.md](docs/11_accessibility.md) |
| **Unit tests + coverage** | [tests/unit/](tests/unit/); whole-suite coverage is 97% and CI fails below 80% |
| **Accounts / external setup** | [docs/09_accounts_and_setup.md](docs/09_accounts_and_setup.md), [.env.example](.env.example) |
| **Professional development** | [docs/08_professional_development_plan.md](docs/08_professional_development_plan.md) |

## Layout

```
app/                 Flask system under test (API + HTML UI)
aws/                 S3 archive, CloudWatch metric, Lambda handler
tests/               pytest suites, grouped by type, shared fixtures in conftest.py
testdata/            static fixtures + factory for unique test data
java-api-tests/      Maven project, JUnit 5 + REST Assured
performance/         JMeter plan
infra/               CloudFormation templates + deploy/destroy scripts for AWS
ai_testing/          AI-assisted generation, predictive flakiness analysis, run history
docs/                STLC artefacts: strategy, plan, cases, defects, risks, agile, AI, growth
Jenkinsfile, .github/workflows/ci.yml, Dockerfile, docker-compose.yml, Makefile
```

## Verified results

| Suite | Target | Result |
|---|---|---|
| Python, 169 tests (unit, api, ui, integration, scale, security, a11y, mobile, aws, ai_testing) | local | 168 passed, 1 skipped (no Appium server) |
| Python smoke, API, security, UI, accessibility | live AWS | 89 passed |
| AI-generated API tests, 45 cases | local and live AWS | 45 passed after fixing the defect they found |
| Java REST Assured | local | 50 passed, the AWS-only class is skipped |
| Java REST Assured with AWS resource checks | live AWS | 61 passed, warm p95 latency 98 ms |
| JMeter, 20 users for 30 s | local | 2,656 requests, 0% errors, p95 8 ms |
| Code coverage of `app/` and `aws/` | local | 97% |
| Jenkins pipeline, all stages | local Jenkins 2.584 | Build passed: 195 tests passed, 1 skipped, in 84 seconds |
| pip-audit, bandit, actionlint | repo | No known vulnerabilities, no findings, clean |

Defects these runs found and fixed are logged as DEF-104 to DEF-108 in [docs/04_defect_management.md](docs/04_defect_management.md).
