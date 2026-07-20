#!/usr/bin/env bash
# Bundle everything needed to debug the stack offline into a tarball:
# container states, inspects, recent logs (secrets redacted), consul
# catalog/intentions, vault status, plugin DB inventory, lock-table state.
set -uo pipefail

cd "$(dirname "$0")/.."
RUNTIME="${RUNTIME:-podman}"
OUT="portal-diagnostics-$(date +%Y%m%d-%H%M%S)"
D=$(mktemp -d)
mkdir -p "$D/$OUT"/{logs,inspect}

echo "==> container states"
"$RUNTIME" ps -a --format '{{.Names}}\t{{.Status}}\t{{.Image}}' | grep backstage | sort \
  > "$D/$OUT/containers.txt" || true

echo "==> logs (last 500 lines each, secrets redacted)"
for c in $("$RUNTIME" ps -a --format '{{.Names}}' | grep backstage); do
  "$RUNTIME" logs --tail 500 "$c" 2>&1 \
    | sed -E 's/(password|token|secret)([":= ]+)[A-Za-z0-9+\/._-]{8,}/\1\2REDACTED/Ig' \
    > "$D/$OUT/logs/$c.log" || true
  "$RUNTIME" inspect "$c" 2>/dev/null \
    | sed -E 's/(PASSWORD|TOKEN|SECRET|KEY)=[^"]*/\1=REDACTED/g' \
    > "$D/$OUT/inspect/$c.json" || true
done

echo "==> consul catalog + intentions"
{
  "$RUNTIME" exec backstage-consul curl -sf --cacert /portal-certs/ca.crt https://127.0.0.1:8501/v1/catalog/services 2>&1
  echo
  for pair in "backstage postgres" "backstage gitea" "gitea postgres" "some-other-svc postgres"; do
    set -- $pair
    echo "intention $1->$2:"
    "$RUNTIME" exec backstage-consul curl -sf --cacert /portal-certs/ca.crt \
      "https://127.0.0.1:8501/v1/connect/intentions/check?source=$1&destination=$2" 2>&1
    echo
  done
} > "$D/$OUT/consul.txt" || true

echo "==> vault status"
"$RUNTIME" exec backstage-vault vault status 2>&1 > "$D/$OUT/vault-status.txt" || true

echo "==> postgres: plugin DBs + lock tables"
"$RUNTIME" exec backstage-postgres sh -c '
psql -U pgadmin -d postgres -c "SELECT datname FROM pg_database WHERE datname LIKE '"'"'backstage%'"'"'"
for db in $(psql -U pgadmin -d postgres -tAc "SELECT datname FROM pg_database WHERE datname LIKE '"'"'backstage%'"'"'"); do
  for t in $(psql -U pgadmin -d "$db" -tAc "SELECT tablename FROM pg_tables WHERE tablename LIKE '"'"'%knex_migrations_lock'"'"'"); do
    echo "$db.$t:"; psql -U pgadmin -d "$db" -c "SELECT * FROM \"$t\""
  done
done' > "$D/$OUT/postgres-locks.txt" 2>&1 || true

tar czf "$OUT.tar.gz" -C "$D" "$OUT"
rm -rf "$D"
echo "collect-diagnostics: wrote ./$OUT.tar.gz"
