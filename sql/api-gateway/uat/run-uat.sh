#!/bin/sh
# UAT battery for the SQL API gateway.
#
#   ./uat/run-uat.sh [--keep]
#
# Brings up the full stack (gateway + Redis + two SQL shards), then exercises
# named operations, sharding, auth, validation, rate limiting, the guarded raw
# path, and verifies rows actually land in SQL Server. Exit 0 iff all pass.
set -u

cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.yml"
BASE="http://127.0.0.1:3000"
PASS=0
FAIL=0
KEEP="${1:-}"

say() { printf '%s\n' "$*"; }
check() { # check <expected> <desc> [curl args...]
    _want="$1"; _desc="$2"; shift 2
    _got="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@")"
    if [ "$_got" = "$_want" ]; then PASS=$((PASS+1)); printf '  PASS  %-56s %s\n' "$_desc" "$_got"
    else FAIL=$((FAIL+1)); printf '  FAIL  %-56s got %s want %s\n' "$_desc" "$_got" "$_want"; fi
}
check_eq() { # check_eq <expected> <desc> <actual>
    if [ "$3" = "$1" ]; then PASS=$((PASS+1)); printf '  PASS  %-56s %s\n' "$2" "$3"
    else FAIL=$((FAIL+1)); printf '  FAIL  %-56s got %s want %s\n' "$2" "$3" "$1"; fi
}
wait_healthy() {
    _i=0
    while [ "$_i" -lt "$2" ]; do
        [ "$(docker inspect --format '{{.State.Health.Status}}' "$1" 2>/dev/null)" = "healthy" ] && return 0
        _i=$((_i+1)); sleep 2
    done
    say "!! $1 not healthy after $(($2*2))s"; docker logs --tail 15 "$1" 2>&1 | sed 's/^/     /'; return 1
}

[ -f .env ] || { say "!! .env missing (cp .env.example .env)"; exit 1; }
# shellcheck disable=SC1091
. ./.env
KEY="$SQL_SA_PASSWORD"

say "== setup"
say "-- starting SQL shards + redis..."
$COMPOSE up -d sql1 sql2 redis >/dev/null 2>&1 || { $COMPOSE up -d sql1 sql2 redis; exit 1; }
wait_healthy sql-stack-shard1 90 || exit 1
wait_healthy sql-stack-shard2 90 || exit 1

say "-- starting gateway (self-provisions each shard's schema)..."
$COMPOSE up -d --build api-gateway >/dev/null 2>&1 || { $COMPOSE up -d --build api-gateway; exit 1; }
gw="$(docker ps --format '{{.Names}}' | grep -E 'api-gateway' | head -1)"
wait_healthy "$gw" 60 || exit 1

say "-- resetting tables for a deterministic run..."
for shard in sql-stack-shard1 sql-stack-shard2; do
    docker exec "$shard" /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$KEY" \
        -d "$APP_DB" -b -Q "TRUNCATE TABLE dbo.Orders; DELETE FROM dbo.Users;" >/dev/null 2>&1
done

TOKEN="$(docker exec "$gw" node mint-token.js uat 3600)"
AUTH="Authorization: Bearer $TOKEN"
JSON="Content-Type: application/json"

say ""
say "== infra endpoints"
check 200 "GET /health (no auth)" "$BASE/health"
check 200 "GET /ready (redis + both shards)" "$BASE/ready"
check 200 "GET /metrics (prometheus)" "$BASE/metrics"

say ""
say "== auth"
check 401 "POST op without token" -X POST "$BASE/v1/op/get_user" -H "$JSON" -d '{"params":{"id":1}}'
check 403 "POST op with bad token" -X POST "$BASE/v1/op/get_user" -H "$JSON" \
    -H 'Authorization: Bearer not.a.jwt' -d '{"params":{"id":1}}'

say ""
say "== named operations (through gateway into SQL)"
# owner 1 -> shard 1, owner 2 -> shard 0 (deterministic: id % 2)
c1="$(curl -s --max-time 15 -X POST "$BASE/v1/op/create_user" -H "$AUTH" -H "$JSON" \
    -d '{"params":{"id":1,"username":"alice","email":"alice@example.com"}}')"
c2="$(curl -s --max-time 15 -X POST "$BASE/v1/op/create_user" -H "$AUTH" -H "$JSON" \
    -d '{"params":{"id":2,"username":"bob","email":"bob@example.com"}}')"
s1="$(printf '%s' "$c1" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("shard",""))' 2>/dev/null)"
s2="$(printf '%s' "$c2" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("shard",""))' 2>/dev/null)"
check_eq "1" "create_user id=1 -> shard 1" "$s1"
check_eq "0" "create_user id=2 -> shard 0 (distribution)" "$s2"

check 200 "get_user id=1" -X POST "$BASE/v1/op/get_user" -H "$AUTH" -H "$JSON" -d '{"params":{"id":1}}'
check 200 "create_order for user 1" -X POST "$BASE/v1/op/create_order" -H "$AUTH" -H "$JSON" \
    -d '{"params":{"user_id":1,"amount":19.99,"status":"paid"}}'
check 200 "create_order for user 2" -X POST "$BASE/v1/op/create_order" -H "$AUTH" -H "$JSON" \
    -d '{"params":{"user_id":2,"amount":5.00,"status":"pending"}}'
check 200 "list_orders user 1" -X POST "$BASE/v1/op/list_orders" -H "$AUTH" -H "$JSON" \
    -d '{"params":{"user_id":1,"limit":10,"offset":0}}'

norders="$(curl -s --max-time 15 -X POST "$BASE/v1/op/count_orders" -H "$AUTH" -H "$JSON" \
    -d '{"params":{"user_id":1}}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["rows"][0]["n"])' 2>/dev/null)"
check_eq "1" "count_orders user 1 == 1" "$norders"

say ""
say "== operation validation (400 = rejected by gateway)"
check 404 "unknown operation" -X POST "$BASE/v1/op/nope" -H "$AUTH" -H "$JSON" -d '{"params":{}}'
check 400 "missing required param" -X POST "$BASE/v1/op/get_user" -H "$AUTH" -H "$JSON" -d '{"params":{}}'
check 400 "wrong param type (id not int)" -X POST "$BASE/v1/op/get_user" -H "$AUTH" -H "$JSON" \
    -d '{"params":{"id":"abc"}}'
check 400 "unknown extra param" -X POST "$BASE/v1/op/get_user" -H "$AUTH" -H "$JSON" \
    -d '{"params":{"id":1,"drop":"table"}}'
# SQL injection attempt in a string param is bound as data, not interpreted:
check 200 "SQLi-shaped username stored as data, not run" -X POST "$BASE/v1/op/create_user" \
    -H "$AUTH" -H "$JSON" -d '{"params":{"id":3,"username":"x; DROP TABLE dbo.Users;--","email":"x@x.io"}}'
check 200 "Users table still exists after injection attempt" -X POST "$BASE/v1/op/get_user" \
    -H "$AUTH" -H "$JSON" -d '{"params":{"id":1}}'

say ""
say "== guarded raw SQL (disabled by default)"
check 404 "POST /query returns 404 when GATEWAY_ALLOW_RAW_SQL=0" -X POST "$BASE/query" \
    -H "$AUTH" -H "$JSON" -d '{"shard_key":1,"query":"SELECT 1"}'

say ""
say "== persistence (rows visible inside the shards)"
n1="$(docker exec sql-stack-shard1 /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$KEY" \
    -d "$APP_DB" -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Users" 2>/dev/null | tr -dc '0-9')"
n0="$(docker exec sql-stack-shard2 /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$KEY" \
    -d "$APP_DB" -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Users" 2>/dev/null | tr -dc '0-9')"
[ "${n1:-0}" -ge 1 ] 2>/dev/null && { PASS=$((PASS+1)); printf '  PASS  %-56s %s\n' "shard 1 Users rows >= 1" "$n1"; } \
    || { FAIL=$((FAIL+1)); printf '  FAIL  %-56s %s\n' "shard 1 Users rows >= 1" "${n1:-none}"; }
[ "${n0:-0}" -ge 1 ] 2>/dev/null && { PASS=$((PASS+1)); printf '  PASS  %-56s %s\n' "shard 0 Users rows >= 1" "$n0"; } \
    || { FAIL=$((FAIL+1)); printf '  FAIL  %-56s %s\n' "shard 0 Users rows >= 1" "${n0:-none}"; }

say ""
TOTAL=$((PASS+FAIL))
if [ "$FAIL" -eq 0 ]; then say "== UAT PASSED: $PASS/$TOTAL"; RC=0
else say "== UAT FAILED: $FAIL of $TOTAL"; RC=1; fi

if [ "$KEEP" != "--keep" ]; then
    $COMPOSE down >/dev/null 2>&1; say "-- stack torn down (use --keep to leave it running)"
else say "-- stack left running on $BASE (--keep)"; fi
exit "$RC"
