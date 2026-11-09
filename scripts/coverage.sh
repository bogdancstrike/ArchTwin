#!/usr/bin/env bash
# Whole-system Python coverage: unit + integration + e2e (API and worker run under coverage.py).
# Needs the stack from `make up` (and `make fixtures-up` for the connector e2e tests; they skip otherwise).
# Usage: scripts/coverage.sh [fail_under]   (default 90)
set -euo pipefail
cd "$(dirname "$0")/.."
FAIL_UNDER="${1:-90}"
DATA=apps/api/.coverage-data
DC="docker compose -f compose.yaml -f compose.coverage.yaml"

# Fresh, world-writable data dir: the containers run as uid 10001.
find "$DATA" -mindepth 1 -delete 2>/dev/null || true
mkdir -p "$DATA" && chmod 777 "$DATA"
restore() { docker compose up -d --wait api worker >/dev/null 2>&1 || true; }
trap restore EXIT

echo "==> instrumented api + worker"
$DC up -d --build --wait --wait-timeout 300 api worker

cd apps/api
export COVERAGE_FILE=.coverage-data/.coverage
echo "==> unit";        uv run coverage run -m pytest -q
echo "==> integration"; uv run coverage run -m pytest -q -m integration tests/integration
echo "==> e2e";         uv run coverage run -m pytest -q -m e2e tests/e2e
cd ../..
if [ "${WITH_UI:-1}" = "1" ]; then echo "==> ui"; (cd apps/web && npx playwright test); fi

echo "==> cli (seed is idempotent; audit verify checks every org's hash chain)"
COV="coverage run --rcfile=/app/pyproject.toml --data-file=/cov/.coverage"
$DC run --rm --no-deps api $COV -m archtwin.cli seed
$DC run --rm --no-deps api $COV -m archtwin.cli audit verify >/dev/null
$DC exec -T worker $COV -m archtwin.worker.alive

echo "==> flushing server-side coverage (graceful stop)"
$DC stop api worker
cd apps/api
uv run coverage combine -q .coverage-data
uv run coverage report --fail-under="$FAIL_UNDER"
uv run coverage xml -q -o .coverage-data/coverage.xml
