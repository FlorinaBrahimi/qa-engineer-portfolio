# Deploying the demo app to AWS

What gets created (all inside the free tier or fractions of a cent per month):

| Resource | Purpose |
|---|---|
| Lambda function (Python 3.12) | Runs the same Flask app as local, via `aws/app_handler.py` |
| Lambda Function URL | Public HTTPS endpoint, no API Gateway needed |
| DynamoDB table (on-demand) | Persists submissions across Lambda instances |
| CloudWatch log group + alarm | Logs with 7-day retention; alarm on any invocation error |
| S3 bucket | Holds the uploaded deployment zips |
| IAM role | Least-privilege execution role for the function |

Everything is defined in `template.yaml`. `github-oidc-role.yaml` is a one-time extra that lets
GitHub Actions deploy without storing AWS keys in GitHub.

## 0. Secure the account first (5 minutes)

You created the account with a root email and password. Do these before anything else:

1. Sign in to the console as root, open **IAM > Security credentials**, and **enable MFA** on root.
2. If the root password has ever been shared anywhere (chat, email, notes), **change it** now.
3. Open **Billing > Budgets** and create a zero-spend or $5 budget with an email alert.
4. Never create access keys for root. Create an IAM user instead (next step).

## 1. Create an IAM user for the CLI

Console: **IAM > Users > Create user**, name `qa-deployer`, no console access.
Attach the managed policies `AWSCloudFormationFullAccess`, `AWSLambda_FullAccess`,
`AmazonDynamoDBFullAccess`, `AmazonS3FullAccess`, `CloudWatchFullAccessV2`, `IAMFullAccess`
(needed to create the function's execution role; remove it after the first deploy if you like).
Then **Security credentials > Create access key > Command Line Interface**. Copy both values.

## 2. Install and configure the AWS CLI on this Mac

```bash
brew install awscli
aws configure            # paste the access key id, secret, region (e.g. eu-west-2), output json
aws sts get-caller-identity
```

## 3. Deploy

```bash
make deploy              # packages, uploads, creates/updates the stack, prints the URL
```

First run takes 2-3 minutes. The script ends with a line like
`export BASE_URL=https://xxxx.lambda-url.eu-west-2.on.aws`. Copy it, then:

```bash
export BASE_URL=https://xxxx.lambda-url.eu-west-2.on.aws
pytest -m "smoke or api or security or ui"     # the whole suite against the live stack
open $BASE_URL                                 # the UI in a browser
```

The `scale` tests are excluded from live runs on purpose: Lambda cold starts make the p95
budget unfair, and the JMeter plan is the right tool for load against a deployed stack.

## 4. Continuous delivery from GitHub

1. Push this repo to GitHub.
2. Deploy the OIDC role once:
   ```bash
   aws cloudformation deploy --stack-name submission-service-github-oidc \
     --template-file infra/github-oidc-role.yaml --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides GitHubOrg=<your-github-user> GitHubRepo=<repo-name>
   aws cloudformation describe-stacks --stack-name submission-service-github-oidc \
     --query "Stacks[0].Outputs[0].OutputValue" --output text
   ```
3. In the GitHub repo: **Settings > Environments > New environment** named `aws-demo`.
   Add secrets `AWS_DEPLOY_ROLE_ARN` (the output above) and `SUBMISSION_API_KEY`, and a
   variable `AWS_REGION`.
4. Every push to `main` that passes `Continuous Testing` now runs `.github/workflows/deploy.yml`:
   deploy, then smoke, API and security suites against the live URL, with the HTML report attached.

## 5. Update, pause, destroy

```bash
make deploy              # redeploy after a change
make destroy             # delete the stack and the artifact bucket; nothing left to bill
```

There is no "pause" needed: Lambda and on-demand DynamoDB cost nothing while idle.

## Troubleshooting

- `AccessDenied` on deploy: the IAM user is missing one of the policies in step 1.
- Stack rollback with `CREATE_FAILED` on the function: check the zip was uploaded to the
  bucket printed by the script, and that `infra/requirements-lambda.txt` installed.
- 502 from the URL: `aws logs tail /aws/lambda/submission-service-app --since 10m`.
