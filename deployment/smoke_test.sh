#!/usr/bin/env sh
# End-to-end check of the running Compose stack through the public nginx origin.
# Requires the stack started with ICARE_ALLOW_UNVERIFIED_EXAMPLES=1 (local/CI only).
# Usage: deployment/smoke_test.sh [base_url]
set -eu
BASE="${1:-http://127.0.0.1:7860}"
API="$BASE/api/v1"
JAR="$(mktemp)"; OTHER="$(mktemp)"
trap 'rm -f "$JAR" "$OTHER"' EXIT
field() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

curl -sf "$API/health" >/dev/null || fail "health"
curl -sf "$API/ready" | grep -q '"ready"' || fail "model not ready"
curl -sf "$BASE/" | grep -q '<div id="root">' || fail "frontend index"

job=$(curl -sf -c "$JAR" -b "$JAR" -H "Origin: $BASE" -H 'Content-Type: application/json' \
      -d '{"example_id":"fall_example_01"}' "$API/jobs/example" | field '["job_id"]') || fail "create job"
state=queued
for _ in $(seq 1 120); do
  state=$(curl -sf -b "$JAR" "$API/jobs/$job" | field '["state"]')
  case "$state" in completed|failed|cancelled) break ;; esac
  sleep 2
done
[ "$state" = completed ] || fail "job ended $state"

curl -sf -b "$JAR" "$API/jobs/$job/results" \
  | python3 -c "import json,sys; r=json.load(sys.stdin); assert r['predictions'] and r['poses'], 'empty result'; print('predictions', len(r['predictions']), 'incidents', len(r['incidents']))"
curl -sf -b "$JAR" "$API/jobs/$job/reports/csv" | head -1 | grep -q fall_probability || fail "csv report"
[ "$(curl -s -o /dev/null -w '%{http_code}' -r 0-99 -b "$JAR" "$API/jobs/$job/media")" = 206 ] || fail "range media"
[ "$(curl -s -o /dev/null -w '%{http_code}' -c "$OTHER" "$API/jobs/$job/results")" = 404 ] || fail "other visitor can read results"
[ "$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" -H 'Origin: https://evil.example' \
     -H 'Content-Type: application/json' -d '{"example_id":"fall_example_01"}' "$API/jobs/example")" = 403 ] || fail "cross-origin accepted"
echo "smoke test passed"
