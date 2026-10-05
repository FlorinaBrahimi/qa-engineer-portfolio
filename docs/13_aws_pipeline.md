# AWS-native CI/CD: CodePipeline and CodeBuild

A second, independent pipeline that runs entirely inside AWS. It deploys its own copy of
the app, the stack `submission-service-aws-ci`, so it never competes with GitHub Actions,
which deploys `submission-service`.

## Stages

| Stage | Service | What runs | Definition |
|---|---|---|---|
| Source | CodeConnections | Pulls `main` from GitHub on every push | `infra/pipeline.yaml` |
| Test | CodeBuild | Dependency, code and template scans; full pytest suite with coverage gate; accessibility audit; Java API suite | `infra/buildspec-test.yml` |
| Deploy | CodeBuild | `infra/deploy.sh` against the target stack | `infra/buildspec-deploy.yml` |
| Verify | CodeBuild | Python and Java suites, with AWS resource and posture checks, against the stack just deployed | `infra/buildspec-live.yml` |

Test results appear as CodeBuild test reports, so each build shows pass and fail counts per test.

## Security design

- **No stored GitHub token.** The source uses a CodeConnections GitHub App connection, and the pipeline role may use it for this one repository only.
- **No secrets in the repository or buildspecs.** The API key is an SSM Parameter Store SecureString, injected into the build at run time.
- **Separate roles.** The test build can write logs and reports and nothing else. Only the deploy and verify builds can touch AWS resources, and only those named after the target stack.
- **Artifacts** are encrypted, private and expire after 14 days.

## Set up

```bash
make aws-pipeline-connection   # creates the GitHub connection (PENDING) and prints the console link
# In the console: open the pending connection, "Update pending connection", "Install a new app",
# grant it the repository, then "Connect". This browser step cannot be scripted.
make aws-pipeline              # stores an API key and creates the pipeline
make aws-pipeline-status       # stage-by-stage status of the latest run
infra/pipeline-setup.sh destroy   # remove everything this created
```

**Install the app, do not only authorise it.** A connection can reach AVAILABLE without the
AWS Connector for GitHub app being installed on the repository. The pipeline can then still
read a public repository, so the first run passes, but GitHub sends it no push events and
later pushes never start a run. Check https://github.com/settings/installations lists
"AWS Connector for GitHub" with access to the repository.

The IAM user running these needs the permissions in `infra/pipeline-user-policy.json`, plus
the AWS-managed CodeBuild and CodePipeline policies.

## Cost

CodeBuild's free tier covers 100 minutes a month on the small instance used here, and a
V2 pipeline has 100 free action-minutes a month. One run takes roughly ten minutes across its
three builds. Beyond the free tier the charge is a fraction of a US cent per minute.

## Compared with the other two pipelines

| | GitHub Actions | Jenkins | AWS CodePipeline |
|---|---|---|---|
| Runs on | GitHub's machines | This Mac | AWS |
| Deploys | `submission-service` | Nothing | `submission-service-aws-ci` |
| Cloud credentials | Short-lived OIDC role | None | IAM service roles |
| Cost | Free for a public repository | Free | Free tier, then per minute |
