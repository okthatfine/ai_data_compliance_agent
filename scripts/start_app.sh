#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
scripts/start_postgres.sh
.venv/bin/python scripts/init_db.py
.venv/bin/python scripts/import_policies_to_db.py
if [ -f app.pid ] && kill -0 "$(cat app.pid)" 2>/dev/null; then
  kill "$(cat app.pid)" || true
  sleep 1
fi
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8018 > server.log 2>&1 & echo $! > app.pid
echo "FastAPI started with PID $(cat app.pid)"
echo "Open http://127.0.0.1:8018/ through SSH tunnel"