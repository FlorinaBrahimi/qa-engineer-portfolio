#!/usr/bin/env bash
# Tear everything down so nothing bills. Usage: infra/destroy.sh [stack-name]
set -euo pipefail
STACK="${1:-submission-service}"
REGION="${AWS_REGION:-$(aws configure get region || echo eu-west-2)}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${STACK}-artifacts-${ACCOUNT}"

echo "==> Deleting stack $STACK"
aws cloudformation delete-stack --region "$REGION" --stack-name "$STACK"
aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$STACK"
echo "==> Emptying and deleting artifact bucket $BUCKET"
aws s3 rm "s3://$BUCKET" --recursive --only-show-errors || true
aws s3api delete-bucket --bucket "$BUCKET" --region "$REGION" || true
echo "==> Done"
