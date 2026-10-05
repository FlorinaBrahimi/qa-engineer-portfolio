# Accounts and External Setup

Most of this project runs with **no accounts at all**: AWS calls are mocked with moto, the app
runs in-process, and CI files are static. Create accounts only for the rows you want to use live.

| Service | Needed for | Required? | Cost | Sign up | Where the credential goes |
|---|---|---|---|---|---|
| GitHub | Hosting the repo, running `.github/workflows/ci.yml` | Yes, to show CI | Free | https://github.com/signup | Push the repo; Actions run automatically |
| Anthropic Console | Real runs of `ai_testing/generate_tests.py` | Optional (`--dry-run` works without) | Pay as you go, small credit needed | https://console.anthropic.com | `ANTHROPIC_API_KEY` in `.env` |
| AWS | Deploying the live demo stack (`infra/`) and running `aws/` code for real | Optional (tests use moto) | Free tier, card required | https://aws.amazon.com/free | `aws configure` with an IAM user's access keys; full runbook in [infra/README.md](../infra/README.md) |
| Docker Hub | Pulling base images for `Dockerfile` | Optional (anonymous pulls work) | Free | https://hub.docker.com/signup | `docker login` only if rate-limited |
| Jenkins | Running the `Jenkinsfile` | No account; self-hosted | Free | Run locally: `docker run -p 8080:8080 jenkins/jenkins:lts` | Add credential id `submission-api-key` in Jenkins |
| BrowserStack or Sauce Labs | Real-device Appium run in `tests/mobile/` | Optional (emulation tests run without) | Free trial | https://www.browserstack.com/users/sign_up | `APPIUM_SERVER_URL` in `.env` |
| JMeter | Running `performance/*.jmx` | No account | Free | `brew install jmeter` | none |

## After signing up

1. Copy `.env.example` to `.env` and fill in only the keys you have. `.env` is git-ignored.
2. Load it before running: `set -a; source .env; set +a`.
3. Check each integration:

```bash
python ai_testing/generate_tests.py --spec-file testdata/openapi_snapshot.json   # Anthropic
aws sts get-caller-identity                                                       # AWS
pytest tests/mobile -m mobile                                                     # Appium
```

## AWS specifics for this project

Create an IAM user with programmatic access and a minimal policy: `s3:PutObject`, `s3:GetObject`
on one bucket, `cloudwatch:PutMetricData`, and `lambda:InvokeFunction` if you deploy the handler.
Never use the root account keys. Enable MFA on the root account and set a billing alarm at a
few dollars before doing anything else.

## Anthropic credentials for the AI test generator

1. Sign in at https://console.anthropic.com and add a small amount of credit under **Billing**.
2. Open **API keys**, click **Create key**, name it `qa-portfolio`, and copy the value. It starts with `sk-ant-` and is shown once.
3. Put it in `.env` in the project root (the file is git-ignored). Never paste it into chat or commit it:

   ```bash
   cp .env.example .env        # only if .env does not exist yet
   # then edit .env and set:  ANTHROPIC_API_KEY=sk-ant-...
   ```

4. Load it into your terminal and run the generator against the local contract snapshot:

   ```bash
   set -a; source .env; set +a
   python ai_testing/generate_tests.py --spec-file testdata/openapi_snapshot.json
   pytest ai_testing/generated/ -v
   ```

One run costs a few cents. For CI, add the same value as a repository secret named
`ANTHROPIC_API_KEY` under **Settings > Secrets and variables > Actions**.
