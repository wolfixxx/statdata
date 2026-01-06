#!/usr/bin/env bash
set -euo pipefail

# Run from project root: ./scripts/smoke_test.sh
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY="${PYTHON:-python3}"
ENV_PREFIX="PYTHONPATH=src"

run() {
  echo
  echo "==> $*"
  eval "$ENV_PREFIX $PY -m statdata.cli $*"
}

echo "Project: $ROOT_DIR"
echo "Python: $($PY --version)"
echo "PYTHONPATH=src"

# Basic
run "sources"

# Eurostat (full)
run "datasets eurostat --max 5"
run "describe eurostat LFSQ_UGAD"
run "codes eurostat LFSQ_UGAD geo --max 5"
run "fetch eurostat LFSQ_UGAD \
  --filter freq=Q --filter unit=THS_PER --filter sex=T --filter age=Y15-74 --filter duration=TOTAL --filter geo=IT \
  --start 2018-Q1 --end 2019-Q4 --head 3"

# ECB (discovery)
run "datasets ecb --max 5"
run "describe ecb EXR"

# OECD (discovery via REST path in discovery.py)
run "datasets oecd --max 5"

# IMF (struct + data)
run "datasets imf --max 5"
run "datasets imf_data --max 5"

# BIS / ISTAT / UNSD (smoke)
run "datasets bis --max 5"
run "datasets istat --max 5"
run "datasets unsd --max 5"

echo
echo "SMOKE TEST: OK"
