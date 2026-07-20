#!/usr/bin/env bash
# Repair `MigrationLocked: Migration table is already locked` crash loops.
#
# Root causes seen in practice:
#   - a crashed portal boot strands is_locked=1 rows (each crash re-strands
#     more, so the loop never converges on its own)
#   - DUPLICATE rows in a *_knex_migrations_lock table make the lock
#     permanently unacquirable — knex expects exactly one row
#
# Procedure (safe: no schema/data changes): stop both portal replicas so
# nothing is migrating, dedupe + unlock every lock table in every
# backstage database, then boot A alone (migrations) and B after.
set -euo pipefail

cd "$(dirname "$0")/.."
RUNTIME="${RUNTIME:-podman}"

echo "==> stopping portal replicas (locks must be swept with no migrator running)"
"$RUNTIME" stop -t 5 backstage-portal-a backstage-portal-b >/dev/null 2>&1 || true

echo "==> dedupe + unlock all knex lock tables"
"$RUNTIME" exec backstage-postgres sh -c '
for db in $(psql -U pgadmin -d postgres -tAc "SELECT datname FROM pg_database WHERE datname LIKE '"'"'backstage%'"'"'"); do
  for t in $(psql -U pgadmin -d "$db" -tAc "SELECT tablename FROM pg_tables WHERE tablename LIKE '"'"'%knex_migrations_lock'"'"'"); do
    rows=$(psql -U pgadmin -d "$db" -tAc "SELECT count(*) FROM \"$t\"")
    if [ "$rows" -gt 1 ]; then
      psql -U pgadmin -d "$db" -qc "DELETE FROM \"$t\" WHERE index NOT IN (SELECT min(index) FROM \"$t\")"
      echo "    deduped $db.$t ($rows rows -> 1)"
    fi
    psql -U pgadmin -d "$db" -qc "UPDATE \"$t\" SET is_locked=0 WHERE is_locked=1"
  done
done
echo "    sweep complete"'

echo "==> booting deployment A (applies any pending migrations alone)"
"$RUNTIME" start backstage-portal-a >/dev/null
for i in $(seq 1 60); do
  CODE=$("$RUNTIME" exec backstage-portal-a curl -sf -o /dev/null -w '%{http_code}' \
    http://127.0.0.1:7007/.backstage/health/v1/readiness 2>/dev/null || echo down)
  [ "$CODE" = "200" ] && break
  [ "$i" = 60 ] && { echo "FAIL: portal A not ready"; "$RUNTIME" logs --tail 15 backstage-portal-a; exit 1; }
  sleep 5
done
echo "    A ready"

echo "==> booting deployment B"
"$RUNTIME" start backstage-portal-b >/dev/null
for i in $(seq 1 60); do
  CODE=$("$RUNTIME" exec backstage-portal-b curl -sf -o /dev/null -w '%{http_code}' \
    http://127.0.0.1:7007/.backstage/health/v1/readiness 2>/dev/null || echo down)
  [ "$CODE" = "200" ] && break
  [ "$i" = 60 ] && { echo "FAIL: portal B not ready"; "$RUNTIME" logs --tail 15 backstage-portal-b; exit 1; }
  sleep 5
done
echo "    B ready"
echo "fix-migration-locks: DONE"
