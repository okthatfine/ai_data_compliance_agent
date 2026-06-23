#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PGROOT="$PWD/vendor/pgsql"
export PATH="$PGROOT/usr/lib/postgresql/14/bin:$PGROOT/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PGROOT/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
mkdir -p data pg_run
if [ ! -x "$PGROOT/usr/lib/postgresql/14/bin/postgres" ]; then
  echo "PostgreSQL binaries not found under vendor/pgsql. Run scripts/setup_portable_postgres.sh first." >&2
  exit 1
fi
if [ ! -s data/pg14/PG_VERSION ]; then
  initdb -D data/pg14 --encoding=UTF8 --locale=C.UTF-8 --auth=trust
fi
if pg_ctl -D data/pg14 status >/dev/null 2>&1; then
  echo "PostgreSQL already running"
else
  pg_ctl -D data/pg14 -l data/pg14.log -o "-p 55432 -k $PWD/pg_run" start
fi
sleep 1
createdb -h 127.0.0.1 -p 55432 compliance_db 2>/dev/null || true
psql -h 127.0.0.1 -p 55432 -d compliance_db -Atc "select 'postgresql ' || version();" | head -1