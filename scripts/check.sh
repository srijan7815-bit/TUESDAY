#!/usr/bin/env bash
set -euo pipefail

readonly PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PYTHON_BIN="${PYTHON_BIN:-${PROJECT_ROOT}/.venv/bin/python}"
readonly TEMP_DIR="$(mktemp -d -t tuesday-check.XXXXXX)"
trap 'rm -rf -- "${TEMP_DIR}"' EXIT
cd "${PROJECT_ROOT}"

export PYTHONPATH="${PROJECT_ROOT}/services/api"
"${PYTHON_BIN}" -m compileall -q services/api/app services/api/tests
"${PYTHON_BIN}" -m ruff check services/api/app services/api/migrations services/api/tests
"${PYTHON_BIN}" -m ruff format --check services/api/app services/api/migrations services/api/tests
"${PYTHON_BIN}" -m mypy services/api/app --ignore-missing-imports --show-error-codes
"${PYTHON_BIN}" -m pytest -q services/api/tests

node --check services/api/app/static/app.js
node --check services/api/app/static/service-worker.js
node --check services/api/app/static/offline.js
bash -n scripts/dev.sh scripts/check.sh clients/android/gradlew \
    clients/linux/src/tuesday-desktop clients/linux/build-deb.sh clients/linux/test.sh

(
    cd services/api
    export TUESDAY_DATABASE_URL="sqlite+aiosqlite:///${TEMP_DIR}/migration.db"
    "${PYTHON_BIN}" -m alembic upgrade head
    "${PYTHON_BIN}" -m alembic downgrade base
    "${PYTHON_BIN}" -m alembic upgrade head
)

"${PYTHON_BIN}" scripts/check-secrets.py
"${PYTHON_BIN}" scripts/validate-config.py
clients/linux/test.sh
echo "All local checks passed"
