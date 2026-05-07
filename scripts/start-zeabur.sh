#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-3000}"

/app/.venv/bin/uvicorn app.main:app --app-dir /app/backend --host 127.0.0.1 --port 8000 &
backend_pid="$!"

cleanup() {
  kill "$backend_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd /app/frontend
npm run start -- -p "$PORT"
