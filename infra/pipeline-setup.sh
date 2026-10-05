#!/usr/bin/env bash
# Create or update the AWS-native pipeline. Safe to re-run.
#
#   infra/pipeline-setup.sh connection     # step 1: create the GitHub connection (then authorise it in the console)
#   infra/pipeline-setup.sh deploy         # step 2: store an API key and create the pipeline
#   infra/pipeline-setup.sh status         # show the latest execution
#   infra/pipeline-setup.sh destroy        # remove the pipeline, its target stack and the connection
set -euo pipefail

REGION="${AWS_REGION:-eu-west-2}"
PIPELINE_STACK="submission-service-pipeline"
TARGET_STACK="submission-service-aws-ci"
PARAM="/${TARGET_STACK}/api-key"
CONN_NAME="${CONNECTION_NAME:-qa-engineer-portfolio}"   # the connection created in the AWS console
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

conn_arn() { aws codeconnections list-connections --region "$REGION" --query "Connections[?ConnectionName=='${CONN_NAME}'].ConnectionArn | [0]" --output text; }
conn_status() { aws codeconnections get-connection --region "$REGION" --connection-arn "$1" --query "Connection.ConnectionStatus" --output text; }

case "${1:-}" in
  connection)
    ARN="$(conn_arn)"
    if [ "$ARN" = "None" ] || [ -z "$ARN" ]; then
      ARN="$(aws codeconnections create-connection --region "$REGION" --provider-type GitHub --connection-name "$CONN_NAME" --query ConnectionArn --output text)"
    fi
    echo "Connection: $ARN"
    echo "Status:     $(conn_status "$ARN")"
    echo "If PENDING, authorise it here:"
    echo "  https://${REGION}.console.aws.amazon.com/codesuite/settings/connections?region=${REGION}"
    ;;
  deploy)
    ARN="$(conn_arn)"
    [ "$(conn_status "$ARN")" = "AVAILABLE" ] || { echo "The GitHub connection is not AVAILABLE yet. Authorise it in the console first." >&2; exit 1; }
    if ! aws ssm get-parameter --region "$REGION" --name "$PARAM" >/dev/null 2>&1; then
      aws ssm put-parameter --region "$REGION" --name "$PARAM" --type SecureString \
        --value "sk-sub-$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" >/dev/null
      echo "Stored a new API key in SSM Parameter Store at $PARAM"
    fi
    aws cloudformation deploy --region "$REGION" --stack-name "$PIPELINE_STACK" \
      --template-file "$ROOT/infra/pipeline.yaml" --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset \
      --parameter-overrides ConnectionArn="$ARN" TargetStackName="$TARGET_STACK" ApiKeyParameterName="$PARAM"
    aws cloudformation describe-stacks --region "$REGION" --stack-name "$PIPELINE_STACK" --query "Stacks[0].Outputs[?OutputKey=='PipelineConsoleUrl'].OutputValue" --output text
    ;;
  status)
    aws codepipeline get-pipeline-state --region "$REGION" --name "$PIPELINE_STACK" \
      --query "stageStates[].[stageName, latestExecution.status]" --output table
    ;;
  destroy)
    for S in "$TARGET_STACK" "$PIPELINE_STACK"; do
      B=$(aws cloudformation describe-stack-resources --region "$REGION" --stack-name "$S" --query "StackResources[?ResourceType=='AWS::S3::Bucket'].PhysicalResourceId" --output text 2>/dev/null || true)
      for bucket in $B; do aws s3 rm "s3://$bucket" --recursive --only-show-errors || true; done
      aws cloudformation delete-stack --region "$REGION" --stack-name "$S"
      aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$S"
      echo "deleted $S"
    done
    ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
    aws s3 rm "s3://${TARGET_STACK}-artifacts-${ACCOUNT}" --recursive --only-show-errors 2>/dev/null || true
    aws s3api delete-bucket --bucket "${TARGET_STACK}-artifacts-${ACCOUNT}" --region "$REGION" 2>/dev/null || true
    aws ssm delete-parameter --region "$REGION" --name "$PARAM" 2>/dev/null || true
    ARN="$(conn_arn)"; [ "$ARN" != "None" ] && aws codeconnections delete-connection --region "$REGION" --connection-arn "$ARN" || true
    ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
