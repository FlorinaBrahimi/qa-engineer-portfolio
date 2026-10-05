#!/usr/bin/env bash
# Deploy the QA Test Plan app and load the manual test cases. Safe to re-run.
# Needs TESTPLAN_KEY in the environment (load .env); it protects recording of results.
set -euo pipefail

REGION="${AWS_REGION:-eu-west-2}"
STACK="qa-test-plan"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${STACK}-artifacts-${ACCOUNT}"
KEY="lambda/$(date +%Y%m%d%H%M%S).zip"

[ -n "${TESTPLAN_KEY:-}" ] || { echo "Set TESTPLAN_KEY first (it is in .env)." >&2; exit 1; }

rm -rf "$ROOT/build/testplan" && mkdir -p "$ROOT/build/testplan/testplan"
cp "$ROOT/testplan/"*.py "$ROOT/build/testplan/testplan/"
(cd "$ROOT/build/testplan" && zip -qr ../testplan.zip .)

if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
fi
aws s3 cp "$ROOT/build/testplan.zip" "s3://$BUCKET/$KEY" --region "$REGION" --only-show-errors

aws cloudformation deploy --region "$REGION" --stack-name "$STACK" --template-file "$ROOT/infra/test-plan.yaml" \
  --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset \
  --parameter-overrides ArtifactBucket="$BUCKET" ArtifactKey="$KEY" TesterKey="$TESTPLAN_KEY"

(cd "$ROOT" && AWS_DEFAULT_REGION="$REGION" python3 -m tools.test_plan_sync --manual testdata/test_plan_manual.json)
URL="$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='TestPlanUrl'].OutputValue" --output text)"
echo "Test plan: $URL"
