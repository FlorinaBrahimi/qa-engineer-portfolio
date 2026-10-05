# Test plan on AWS

AWS has no managed test-management service (nothing equivalent to Azure Test Plans, Xray or
TestRail). This project therefore builds one from AWS parts, so the plan, the manual cases
and the automated results all live in the AWS account.

## What it is

| Part | AWS service | Purpose |
|---|---|---|
| Test case store | DynamoDB table `qa-test-plan-cases` | One item per test case, manual or automated, with its latest result and history |
| Web app | Lambda behind a Function URL (`testplan/handler.py`) | Shows the plan, each case with steps and expected results, and a form to record manual results |
| Loader | `tools/test_plan_sync.py` | Loads manual case definitions; converts JUnit results into automated cases |
| Infrastructure | `infra/test-plan.yaml` | The stack `qa-test-plan` |

## Manual test cases

Twelve cases in `testdata/test_plan_manual.json`, each with an objective, preconditions,
numbered steps and an expected result per step. They cover what automation cannot:
exploratory charters, cross-browser checks, screen reader and voice control passes, a
real-device check, a 50-user load test, a backup restore drill, an alerting drill and
release sign-off.

To execute one: open the case in the app, follow the steps, then record Passed, Failed,
Blocked or Skipped with your name and notes. Recording needs the tester key, `TESTPLAN_KEY`
in `.env`. Every result is kept in the case's history.

All twelve start as "not run". None has been executed yet.

## Automated test cases

After each run, the pipelines publish their JUnit results to the plan:

| Publisher | When |
|---|---|
| AWS CodeBuild, pre-deploy stage | Every pipeline run |
| AWS CodeBuild, live-stack stage | Every pipeline run, after the deploy |
| Jenkins | Every build |

Each automated test becomes a case grouped by suite, showing passed, failed or skipped, its
duration, any failure message and which pipeline reported it. A suite with a failure opens
automatically and is flagged. Automated cases cannot be edited by hand.

## Commands

```bash
set -a; source .env; set +a
make test-plan            # deploy or update the app and reload manual case definitions
make test-plan-sync       # publish the latest local test results
```

Re-loading definitions never resets a recorded manual result.

## Security

Reading the plan is public so it can be shown. Recording a result needs the tester key,
compared in constant time; cross-site form posts are refused; all output is escaped; the
same security headers as the main app are sent. The table has point-in-time recovery.

## Limits

This is a purpose-built tool, not a product. It has no user accounts, no test runs or
cycles, no requirement traceability matrix and no attachments. A team needing those would
use Xray or Zephyr in Jira, or TestRail, and keep AWS for execution and reporting.
