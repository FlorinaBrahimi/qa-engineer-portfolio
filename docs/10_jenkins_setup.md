# Running the pipeline in Jenkins

The [Jenkinsfile](../Jenkinsfile) runs on a plain agent. It needs no Docker and only the
plugins a default Jenkins install has: Pipeline, Git, JUnit and Timestamper.

## Agent requirements

| Tool | Used by |
|---|---|
| Python 3.12 | all pytest stages, security scans |
| Java 17+ and Maven | Java API suite |
| JMeter | performance stage |

On macOS with Homebrew: `brew install maven jmeter`, plus Python from python.org or Homebrew.
The Jenkinsfile adds the Homebrew and python.org locations to `PATH` itself, because Jenkins
started as a service has a minimal one.

## Create the job

1. Open Jenkins (locally: http://127.0.0.1:8080) and sign in.
2. **New Item**, name it `qa-engineer-portfolio`, choose **Pipeline**, click **OK**.
3. Under **Pipeline**, set **Definition** to **Pipeline script from SCM**.
4. **SCM**: Git. **Repository URL**: `https://github.com/FlorinaBrahimi/qa-engineer-portfolio.git`.
   The repository is public, so no credentials are needed.
5. **Branch Specifier**: `*/main`. **Script Path**: `Jenkinsfile`. Click **Save**.
6. Click **Build Now**.

The first build takes a few minutes while it creates a virtual environment and installs
dependencies. Later builds reuse the downloaded browser.

## What it does

| Stage | Runs |
|---|---|
| Install | Virtual environment, dependencies, Chromium |
| Smoke | `pytest -m smoke`; the build stops here on failure |
| Test (parallel) | Unit, API, security and AWS tests; UI, accessibility and mobile; integration and scale; pip-audit and bandit; the Java suite against a locally started app |
| Predictive analysis | Flakiness report from run history |
| Performance | JMeter on every build (20 users, 30 s); the nightly run uses 50 users for 120 s. Results join the test report |

Results appear under **Test Result** on the build page, and the HTML reports, JMeter dashboard
and flakiness report are under **Build Artifacts**.

## Triggers

The job polls the repository every 15 minutes and runs nightly at about 02:00. Polling is
used because a Jenkins on a laptop cannot receive GitHub webhooks.

## Relationship to GitHub Actions

GitHub Actions is the pipeline that deploys to AWS. Jenkins runs the same test stages and
shows the role's Jenkins requirement, but it deliberately has no deploy stage, so two systems
never deploy the same stack.
