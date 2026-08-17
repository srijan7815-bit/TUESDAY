#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/services/api"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -U pip
  pip install -r requirements.txt
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
mkdir -p "$ROOT/data"
if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
fi
export TUESDAY_DATA_DIR="${TUESDAY_DATA_DIR:-$ROOT/data}"
export TUESDAY_DATABASE_URL="${TUESDAY_DATABASE_URL:-sqlite+aiosqlite:///$ROOT/data/tuesday.db}"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
