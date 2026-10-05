#!/usr/bin/env bash
# Package the app, upload it, and create/update the CloudFormation stack.
# Usage: infra/deploy.sh [stack-name]   (needs AWS CLI with credentials, and AWS_REGION or a default region)
set -euo pipefail

STACK="${1:-submission-service}"
REGION="${AWS_REGION:-$(aws configure get region || echo eu-west-2)}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${STACK}-artifacts-${ACCOUNT}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build"
ZIP="$BUILD/lambda.zip"
KEY="lambda/$(date +%Y%m%d%H%M%S)-$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo local).zip"

echo "==> Packaging"
rm -rf "$BUILD" && mkdir -p "$BUILD/pkg"
python3 -m pip install -q -r "$ROOT/infra/requirements-lambda.txt" -t "$BUILD/pkg" --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12 --implementation cp
cp -R "$ROOT/app" "$ROOT/aws" "$BUILD/pkg/"
find "$BUILD/pkg" -name "__pycache__" -type d -prune -exec rm -rf {} +
(cd "$BUILD/pkg" && zip -qr "$ZIP" .)
echo "    $(du -h "$ZIP" | cut -f1) $ZIP"

echo "==> Uploading to s3://$BUCKET/$KEY ($REGION)"
if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
  fi
fi
aws s3 cp "$ZIP" "s3://$BUCKET/$KEY" --region "$REGION" --only-show-errors

echo "==> Deploying stack $STACK"
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK" \
  --template-file "$ROOT/infra/template.yaml" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --parameter-overrides ArtifactBucket="$BUCKET" ArtifactKey="$KEY" ApiKey="${SUBMISSION_API_KEY:-qa-demo-key}"

URL="$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='AppUrl'].OutputValue" --output text)"
URL="${URL%/}"
echo "==> Deployed: $URL"
echo "    export BASE_URL=$URL"
echo "==> Health check"
curl -sf "$URL/health" && echo
