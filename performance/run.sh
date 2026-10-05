#!/usr/bin/env bash
# Start the app, run the JMeter plan against it, and convert the results into a JUnit file,
# a Markdown summary and an HTML dashboard. Exits non-zero if a threshold is breached.
#
#   performance/run.sh                 # 20 users for 30 s
#   USERS=50 DURATION=120 performance/run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-python3}"
PORT="${PERF_PORT:-5012}"
USERS="${USERS:-20}"; RAMP="${RAMP:-5}"; DURATION="${DURATION:-30}"
MAX_P95_MS="${MAX_P95_MS:-500}"; MAX_ERROR_PCT="${MAX_ERROR_PCT:-0.5}"

cd "$ROOT"
mkdir -p reports
rm -rf reports/perf-html reports/perf.jtl reports/perf.xml reports/perf.md

PORT="$PORT" "$PY" -m app.server > reports/perf-sut.log 2>&1 &
SUT_PID=$!
trap 'kill $SUT_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 20); do curl -sf "http://localhost:$PORT/health" > /dev/null && break; sleep 1; done

jmeter -n -t performance/submissions_load_test.jmx \
  -Jhost=localhost -Jport="$PORT" -Jusers="$USERS" -Jramp="$RAMP" -Jduration="$DURATION" \
  -l reports/perf.jtl -e -o reports/perf-html | grep -E "summary =|Err:" | tail -1

"$PY" -m tools.jmeter_report reports/perf.jtl --junit reports/perf.xml --markdown reports/perf.md \
  --max-p95-ms "$MAX_P95_MS" --max-error-pct "$MAX_ERROR_PCT"
