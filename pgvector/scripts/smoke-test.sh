#!/usr/bin/env bash
# Smoke test for the pgvector stack: health, extension, schema, role
# separation (app_ro cannot write), and a vector round-trip.
set -euo pipefail

cd "$(dirname "$0")/.."

RUNTIME="${RUNTIME:-podman}"

[ -s .env ] || { echo "FAIL: pgvector/.env missing — run ./scripts/bootstrap-env.sh"; exit 1; }
# shellcheck disable=SC1091
. ./.env

PASS=0
FAIL=0
check() { # check <description> <expected> <actual>
  if [ "$3" = "$2" ]; then
    PASS=$((PASS + 1)); printf '  PASS  %-52s %s\n' "$1" "$3"
  else
    FAIL=$((FAIL + 1)); printf '  FAIL  %-52s got %s want %s\n' "$1" "$3" "$2"
  fi
}
# Connect via the container's bridge IP, not loopback: the image's default
# pg_hba trusts in-container loopback, so only the network path exercises
# real scram authentication.
sql() { # sql <role> <password> <query>
  "$RUNTIME" exec -e PGPASSWORD="$2" pgvector-main \
    psql -h "$PG_IP" -U "$1" -d "$POSTGRES_DB" -tA -c "$3" 2>&1 | head -1
}

echo "==> waiting for postgres health"
for i in $(seq 1 30); do
  if [ "$("$RUNTIME" inspect --format '{{.State.Health.Status}}' pgvector-main 2>/dev/null)" = "healthy" ]; then
    break
  fi
  [ "$i" = 30 ] && { echo "FAIL: pgvector-main never became healthy"; exit 1; }
  sleep 2
done
echo "    healthy"
PG_IP=$("$RUNTIME" inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' pgvector-main)

echo "==> schema and extension"
check "pgvector extension installed" 0.8.5 \
  "$(sql "$POSTGRES_USER" "$POSTGRES_PASSWORD" "SELECT extversion FROM pg_extension WHERE extname='vector'")"
check "documents table exists" documents \
  "$(sql "$POSTGRES_USER" "$POSTGRES_PASSWORD" "SELECT tablename FROM pg_tables WHERE tablename='documents'")"
check "hnsw index exists" documents_embedding_idx \
  "$(sql "$POSTGRES_USER" "$POSTGRES_PASSWORD" "SELECT indexname FROM pg_indexes WHERE indexname='documents_embedding_idx'")"

echo "==> authentication and role separation"
check "bad password rejected" 2 \
  "$(sql "$POSTGRES_USER" wrong-password 'SELECT 1' >/dev/null 2>&1; echo $?)"
check "app_rw can insert" INSERT \
  "$(sql app_rw "$APP_RW_PASSWORD" "INSERT INTO documents VALUES (999901,'smoke','smoke',2026,'[$(python3 -c 'print(",".join(["0.1"]*384))')]') " | cut -d' ' -f1)"
check "app_ro can read" 1 \
  "$(sql app_ro "$APP_RO_PASSWORD" "SELECT count(*) FROM documents WHERE id=999901")"
check "app_ro cannot write" ERROR \
  "$(sql app_ro "$APP_RO_PASSWORD" "DELETE FROM documents WHERE id=999901" | cut -d: -f1)"

echo "==> vector round-trip"
check "nearest-neighbour search returns the row" 999901 \
  "$(sql app_ro "$APP_RO_PASSWORD" "SELECT id FROM documents ORDER BY embedding <=> '[$(python3 -c 'print(",".join(["0.1"]*384))')]' LIMIT 1")"
check "cleanup" DELETE \
  "$(sql app_rw "$APP_RW_PASSWORD" "DELETE FROM documents WHERE id=999901" | cut -d' ' -f1)"

echo
echo "smoke test: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
