#!/bin/sh
# Stress test the SQL gateway under extreme load with k6.
#
#   ./stress/run-stress.sh [--keep] [VUS] [DURATION] [GATEWAY_REPLICAS]
#   ./stress/run-stress.sh --keep 100 60s 3
#
# Brings up the stack (rate limiting raised so throughput isn't capped),
# optionally scales the gateway, seeds owners, then runs k6 from a container
# on the edge network. Prints k6's summary and passes/fails on its thresholds
# (error rate <1%, p95 <500ms, p99 <1500ms).
set -u

cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.yml"
KEEP=""
[ "${1:-}" = "--keep" ] && { KEEP=1; shift; }
VUS="${1:-50}"
DURATION="${2:-30s}"
REPLICAS="${3:-1}"

say() { printf '%s\n' "$*"; }
wait_healthy() {
    _i=0
    while [ "$_i" -lt "$2" ]; do
        [ "$(docker inspect --format '{{.State.Health.Status}}' "$1" 2>/dev/null)" = "healthy" ] && return 0
        _i=$((_i+1)); sleep 2
    done
    say "!! $1 not healthy after $(($2*2))s"; return 1
}

[ -f .env ] || { say "!! .env missing (cp .env.example .env)"; exit 1; }

# Raise the limit far above the offered load so the limiter doesn't cap us.
# k6 runs from one container (one source IP), so it shares a single rate-limit
# budget; the normal 100/min would 429 almost everything. Restore .env on exit.
restore_env() { grep -v '^RATE_LIMIT_MAX=' .env > .env.tmp 2>/dev/null && mv .env.tmp .env; }
trap 'restore_env' EXIT INT TERM
restore_env
printf 'RATE_LIMIT_MAX=10000000\n' >> .env

say "== bringing up stack (rate limit raised for load) ..."
$COMPOSE up -d --build sql1 sql2 redis >/dev/null 2>&1 || { $COMPOSE up -d sql1 sql2 redis; exit 1; }
wait_healthy sql-stack-shard1 90 || exit 1
wait_healthy sql-stack-shard2 90 || exit 1
# Recreate the gateway so it picks up the raised rate limit.
docker rm -f sql-stack_api-gateway_1 >/dev/null 2>&1 || true
$COMPOSE up -d --build --no-deps api-gateway >/dev/null 2>&1 || { $COMPOSE up -d api-gateway; exit 1; }

if [ "$REPLICAS" -gt 1 ]; then
    say "== scaling gateway to $REPLICAS replicas ..."
    $COMPOSE up -d --scale api-gateway="$REPLICAS" api-gateway >/dev/null 2>&1 || true
fi

gw="$(docker ps --format '{{.Names}}' | grep -E 'api-gateway' | head -1)"
wait_healthy "$gw" 60 || exit 1
TOKEN="$(docker exec "$gw" node mint-token.js load 7200)"

# Clean slate so the seed step never collides with prior data.
# shellcheck disable=SC1091
. ./.env
for shard in sql-stack-shard1 sql-stack-shard2; do
    docker exec "$shard" /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$SQL_SA_PASSWORD" \
        -d "$APP_DB" -b -Q "TRUNCATE TABLE dbo.Orders; DELETE FROM dbo.Users;" >/dev/null 2>&1
done

NET="$(docker inspect "$gw" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | tr ' ' '\n' | grep -i edge | head -1)"
[ -n "$NET" ] || NET="sql-stack_edge"

say "== running k6: VUS=$VUS DURATION=$DURATION REPLICAS=$REPLICAS ..."
docker run --rm --network "$NET" \
    -e BASE="http://api-gateway:3000" \
    -e TOKEN="$TOKEN" \
    -e VUS="$VUS" \
    -e DURATION="$DURATION" \
    -v "$(pwd)/stress":/scripts:ro,Z \
    docker.io/grafana/k6:latest run /scripts/load.js
RC=$?

say ""
say "== gateway metrics snapshot =="
curl -s "http://127.0.0.1:3000/metrics" 2>/dev/null \
    | grep -E '^gateway_operations_total|^gateway_request_duration_seconds_count' | head -20

if [ -z "$KEEP" ]; then
    $COMPOSE down >/dev/null 2>&1; say "-- stack torn down (use --keep to leave it running)"
else say "-- stack left running (--keep)"; fi
exit "$RC"
