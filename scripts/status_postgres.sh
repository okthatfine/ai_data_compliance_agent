#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PGROOT="$PWD/vendor/pgsql"
export PATH="$PGROOT/usr/lib/postgresql/14/bin:$PGROOT/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PGROOT/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
pg_ctl -D data/pg14 status || exit 1
psql -h 127.0.0.1 -p 55432 -d compliance_db -c "select current_database(), current_user, now();"