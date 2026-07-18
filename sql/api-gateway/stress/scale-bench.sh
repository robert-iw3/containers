#!/bin/sh
# Horizontal-scaling benchmark: run an identical write-heavy load against the
# gateway backed by 1 shard, then by 2 shards, and compare throughput/latency
# and the per-shard write volume. Demonstrates how adding a shard divides the
# write load and adds capacity.
#
#   ./stress/run-... first (this reuses the running shards); or standalone:
#   ./stress/scale-bench.sh [VUS] [DURATION]
set -u

cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.yml"
ONE="-f stress/bench-1shard.yml"
VUS="${1:-80}"; DURATION="${2:-20s}"

say() { printf '%s\n' "$*"; }
wait_healthy() { _i=0; while [ "$_i" -lt "$2" ]; do
    [ "$(docker inspect --format '{{.State.Health.Status}}' "$1" 2>/dev/null)" = "healthy" ] && return 0
    _i=$((_i+1)); sleep 2; done; say "!! $1 not healthy"; return 1; }

[ -f .env ] || { say "!! .env missing"; exit 1; }
# shellcheck disable=SC1091
. ./.env

# Raise rate limit for the run; restore on exit.
restore_env() { grep -v '^RATE_LIMIT_MAX=' .env > .env.tmp 2>/dev/null && mv .env.tmp .env; }
trap 'restore_env' EXIT INT TERM
restore_env; printf 'RATE_LIMIT_MAX=100000000\n' >> .env

reset_tables() {
    for s in sql-stack-shard1 sql-stack-shard2; do
        docker exec "$s" /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$SQL_SA_PASSWORD" \
            -d "$APP_DB" -b -Q "TRUNCATE TABLE dbo.Orders; DELETE FROM dbo.Users;" >/dev/null 2>&1
    done
}
shard_orders() {  # count orders on a shard container
    docker exec "$1" /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$SQL_SA_PASSWORD" \
        -d "$APP_DB" -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Orders" 2>/dev/null | tr -dc '0-9'
}

say "== bringing up shards + redis =="
$COMPOSE up -d --build sql1 sql2 redis >/dev/null 2>&1 || { $COMPOSE up -d sql1 sql2 redis; exit 1; }
wait_healthy sql-stack-shard1 120 || exit 1
wait_healthy sql-stack-shard2 120 || exit 1

NET=sql-stack_edge

run_scenario() {  # run_scenario <label> <compose-extra>
    label="$1"; extra="$2"
    docker rm -f sql-stack_api-gateway_1 >/dev/null 2>&1
    # shellcheck disable=SC2086
    $COMPOSE $extra up -d --build --no-deps api-gateway >/dev/null 2>&1 || $COMPOSE $extra up -d api-gateway >/dev/null 2>&1
    wait_healthy sql-stack_api-gateway_1 60 || return 1
    reset_tables
    TOKEN="$(docker exec sql-stack_api-gateway_1 node mint-token.js bench 3600)"
    docker run --rm --network "$NET" \
        -e BASE=http://api-gateway:3000 -e TOKEN="$TOKEN" -e VUS="$VUS" -e DURATION="$DURATION" -e OWNERS=400 \
        -v "$(pwd)/stress":/scripts:ro,Z docker.io/grafana/k6:latest run /scripts/scale-bench.js >/tmp/bench.out 2>&1
    thr="$(grep -E 'http_reqs' /tmp/bench.out | grep -oE '[0-9]+\.[0-9]+/s' | head -1)"
    p95="$(grep -E 'http_req_duration' /tmp/bench.out | grep -oE 'p\(95\)=[0-9.]+m?s' | head -1)"
    fail="$(grep -E 'http_req_failed' /tmp/bench.out | grep -oE '[0-9.]+%' | head -1)"
    o0="$(shard_orders sql-stack-shard1)"; o1="$(shard_orders sql-stack-shard2)"
    printf '%-9s | %-12s | %-12s | %-7s | shard0=%-6s shard1=%-6s\n' \
        "$label" "${thr:-?}" "${p95:-?}" "${fail:-?}" "${o0:-0}" "${o1:-0}"
}

say ""
say "== write-heavy benchmark (create_order, VUS=$VUS, $DURATION) =="
say "scenario  | throughput   | p95 latency  | errors  | orders written per shard"
say "----------+--------------+--------------+---------+--------------------------"
run_scenario "1-shard" "$ONE"
run_scenario "2-shard" ""

say ""
say "-- tearing down gateway; shards left running (use compose down to stop all)"
docker rm -f sql-stack_api-gateway_1 >/dev/null 2>&1
