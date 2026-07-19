#!/usr/bin/env bash
# UAT battery for the pgvector stack.
#
#   ./run-uat.sh
#
# Phase 1: auth, schema/extension, ingest of the synthetic corpus
#          (2000 docs), HNSW recall, filtered search, update/delete,
#          role separation.
# Phase 2: restarts the postgres container, then verifies the data
#          survived.
# Exit code 0 iff both phases pass.
set -euo pipefail

cd "$(dirname "$0")"

RUNTIME="${RUNTIME:-podman}"
COMPOSE="${COMPOSE:-podman-compose}"

wait_healthy() { # wait_healthy <container> <seconds>
  i=0
  while [ "$i" -lt "$2" ]; do
    if [ "$("$RUNTIME" inspect --format '{{.State.Health.Status}}' "$1" 2>/dev/null)" = "healthy" ]; then
      return 0
    fi
    i=$((i + 1)); sleep 2
  done
  echo "!! $1 not healthy after $((2 * $2))s"
  "$RUNTIME" logs --tail 10 "$1" 2>&1 | sed 's/^/     /'
  return 1
}

echo "== UAT setup"
if [ ! -s ../.env ]; then
  echo "-- no .env; bootstrapping"
  ../scripts/bootstrap-env.sh
fi
if [ "$("$RUNTIME" inspect --format '{{.State.Status}}' pgvector-main 2>/dev/null)" != "running" ]; then
  echo "-- stack not running; starting it"
  (cd .. && $COMPOSE up -d)
fi
wait_healthy pgvector-main 60

echo "-- building UAT image"
$COMPOSE -f docker-compose.uat.yml build uat-runner >/dev/null

echo
echo "== Phase 1: provisioning + functional battery"
$COMPOSE -f docker-compose.uat.yml run --rm uat-runner pytest -q -m "not verify"

echo
echo "== Phase 2: restart postgres, verify persistence"
"$RUNTIME" restart pgvector-main >/dev/null 2>&1 || { sleep 3; "$RUNTIME" restart pgvector-main >/dev/null; }
wait_healthy pgvector-main 60
$COMPOSE -f docker-compose.uat.yml run --rm uat-runner pytest -q -m verify

echo
echo "UAT: all phases passed"
