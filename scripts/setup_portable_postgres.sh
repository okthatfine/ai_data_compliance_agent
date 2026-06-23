#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p vendor/debs vendor/pgsql
cd vendor/debs
apt-get download postgresql-14 postgresql-client-14 postgresql-common postgresql-client-common libpq5 libpq-dev
for deb in *.deb; do dpkg-deb -x "$deb" ../pgsql; done
cd ../..
chmod +x scripts/start_postgres.sh scripts/stop_postgres.sh scripts/status_postgres.sh
scripts/start_postgres.sh