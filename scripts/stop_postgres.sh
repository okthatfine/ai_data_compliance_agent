#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PGROOT="$PWD/vendor/pgsql"
export PATH="$PGROOT/usr/lib/postgresql/14/bin:$PGROOT/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PGROOT/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
if [ -s data/pg14/PG_VERSION ]; then
  pg_ctl -D data/pg14 stop -m fast || true
else
  echo "No data/pg14 cluster found"
fi