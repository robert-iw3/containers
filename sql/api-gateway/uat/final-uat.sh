#!/bin/sh
# Final end-to-end UAT for the SQL stack:
#   load balancer (nginx|haproxy)  ->  3 gateway replicas  ->  tuned SQL shards
#
#   ./uat/final-uat.sh [nginx|haproxy] [--keep]
#
# Verifies, in one run:
#   1. SQL tuning was applied to the shards
#   2. the load balancer spreads traffic across all gateway replicas (channels)
#   3. operations route to the correct shard, and data lands there
#   4. the stack stays performant under load through the LB (k6 thresholds)
#   5. end-to-end read-back through the LB
set -u

cd "$(dirname "$0")/.."

LB="${1:-nginx}"
KEEP=""
[ "${2:-}" = "--keep" ] && KEEP=1
[ "${1:-}" = "--keep" ] && { KEEP=1; LB="nginx"; }
case "$LB" in
  nginx)   PROFILE=lb-nginx;   LBSVC=nginx-lb;   LBPORT=80   ;;
  haproxy) PROFILE=lb-haproxy; LBSVC=haproxy-lb; LBPORT=8080 ;;
  *) echo "usage: final-uat.sh [nginx|haproxy] [--keep]"; exit 2 ;;
esac

BASE="http://127.0.0.1:8088"
COMPOSE="docker compose -f docker-compose.yml -f lb/docker-compose.lb.yml"
PASS=0; FAIL=0

say()  { printf '%s\n' "$*"; }
ok()   { PASS=$((PASS+1)); printf '  PASS  %-56s %s\n' "$1" "${2:-}"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %-56s %s\n' "$1" "${2:-}"; }
chk()  { if [ "$3" = "$2" ]; then ok "$1" "$3"; else bad "$1" "got $3 want $2"; fi; }
http() { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@"; }
wait_healthy() {
    _i=0
    while [ "$_i" -lt "$2" ]; do
        [ "$(docker inspect --format '{{.State.Health.Status}}' "$1" 2>/dev/null)" = "healthy" ] && return 0
        _i=$((_i+1)); sleep 2
    done
    say "!! $1 not healthy after $(($2*2))s"; docker logs --tail 12 "$1" 2>&1 | sed 's/^/     /'; return 1
}

[ -f .env ] || { say "!! .env missing (cp .env.example .env)"; exit 1; }
# shellcheck disable=SC1091
. ./.env
KEY="$SQL_SA_PASSWORD"

# Raise the rate limit so the k6 phase isn't throttled; restore on exit.
restore_env() { grep -v '^RATE_LIMIT_MAX=' .env > .env.tmp 2>/dev/null && mv .env.tmp .env; }
trap 'restore_env' EXIT INT TERM
restore_env; printf 'RATE_LIMIT_MAX=10000000\n' >> .env

say "== bringing up: $LB LB -> 3 gateway replicas -> tuned shards =="
$COMPOSE up -d --build sql1 sql2 redis >/dev/null 2>&1 || { $COMPOSE up -d sql1 sql2 redis; exit 1; }
wait_healthy sql-stack-shard1 120 || exit 1
wait_healthy sql-stack-shard2 120 || exit 1
$COMPOSE --profile "$PROFILE" up -d --build >/dev/null 2>&1 || { $COMPOSE --profile "$PROFILE" up -d; exit 1; }
for c in sql-stack_api-gateway_1 sql-stack-gateway-b sql-stack-gateway-c; do wait_healthy "$c" 60 || exit 1; done
# Wait for the LB to accept traffic (LB containers have no healthcheck).
_i=0; while ! curl -s -o /dev/null --max-time 3 "$BASE/health" && [ "$_i" -lt 30 ]; do _i=$((_i+1)); sleep 1; done

gw=sql-stack_api-gateway_1
for s in sql-stack-shard1 sql-stack-shard2; do
    docker exec "$s" /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$KEY" -d "$APP_DB" -b \
        -Q "TRUNCATE TABLE dbo.Orders; DELETE FROM dbo.Users;" >/dev/null 2>&1
done
TOKEN="$(docker exec "$gw" node mint-token.js finaluat 3600)"
AUTH="Authorization: Bearer $TOKEN"; JSON="Content-Type: application/json"

# ---------------------------------------------------------- 1. tuning ----
say ""
say "== 1. SQL tuning applied to shards =="
cfg() { docker exec sql-stack-shard1 /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$KEY" -h -1 -W \
        -Q "SET NOCOUNT ON; SELECT CAST(value_in_use AS int) FROM sys.configurations WHERE name = '$1'" 2>/dev/null | tr -dc '0-9'; }
chk "max degree of parallelism = 2"       "2"  "$(cfg 'max degree of parallelism')"
chk "cost threshold for parallelism = 50" "50" "$(cfg 'cost threshold for parallelism')"
chk "optimize for ad hoc workloads = 1"   "1"  "$(cfg 'optimize for ad hoc workloads')"
tf="$(docker exec sql-stack-shard1 /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$KEY" -h -1 -W \
      -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM sys.master_files WHERE database_id=2 AND type=0" 2>/dev/null | tr -dc '0-9')"
[ "${tf:-0}" -ge 4 ] 2>/dev/null && ok "tempdb data files >= 4" "$tf" || bad "tempdb data files >= 4" "got ${tf:-0}"
qs="$(docker exec sql-stack-shard1 /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$KEY" -d "$APP_DB" -h -1 -W \
      -Q "SET NOCOUNT ON; SELECT actual_state_desc FROM sys.database_query_store_options" 2>/dev/null | tr -d ' \r\n')"
case "$qs" in READ_WRITE*) ok "Query Store READ_WRITE on $APP_DB" "$qs" ;; *) bad "Query Store READ_WRITE on $APP_DB" "got ${qs:-none}" ;; esac
rcsi="$(docker exec sql-stack-shard1 /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$KEY" -h -1 -W \
       -Q "SET NOCOUNT ON; SELECT is_read_committed_snapshot_on FROM sys.databases WHERE name='$APP_DB'" 2>/dev/null | tr -dc '0-9')"
chk "READ_COMMITTED_SNAPSHOT on $APP_DB"   "1"  "$rcsi"

# --------------------------------------------------- 2. LB routing -------
say ""
say "== 2. load balancer spreads across gateway replicas ($LB) =="
UP="$(for i in $(seq 1 30); do curl -s -D - -o /dev/null --max-time 10 "$BASE/health" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-upstream"{print $2}'; done | sort -u)"
n_up="$(printf '%s\n' "$UP" | grep -c .)"
[ "${n_up:-0}" -ge 3 ] && ok "distinct upstreams served (>=3)" "$n_up" || bad "distinct upstreams served (>=3)" "got ${n_up:-0}: $(echo $UP)"

# --------------------------------------- 3. shard routing + data flow ----
say ""
say "== 3. correct shard routing + data flow (write via LB -> shard) =="
even="$(curl -s --max-time 15 -X POST "$BASE/v1/op/create_user" -H "$AUTH" -H "$JSON" -d '{"params":{"id":10,"username":"even","email":"e@x.io"}}')"
odd="$( curl -s --max-time 15 -X POST "$BASE/v1/op/create_user" -H "$AUTH" -H "$JSON" -d '{"params":{"id":11,"username":"odd","email":"o@x.io"}}')"
se="$(printf '%s' "$even" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("shard",""))' 2>/dev/null)"
so="$(printf '%s' "$odd"  | python3 -c 'import json,sys;print(json.load(sys.stdin).get("shard",""))' 2>/dev/null)"
chk "id=10 (even) routed to shard 0" "0" "$se"
chk "id=11 (odd)  routed to shard 1" "1" "$so"
# Confirm the row physically lives in the expected shard and NOT the other.
d0="$(docker exec sql-stack-shard1 /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$KEY" -d "$APP_DB" -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Users WHERE id=10" 2>/dev/null | tr -dc '0-9')"
d1="$(docker exec sql-stack-shard2 /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$KEY" -d "$APP_DB" -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Users WHERE id=11" 2>/dev/null | tr -dc '0-9')"
x0="$(docker exec sql-stack-shard1 /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P "$KEY" -d "$APP_DB" -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Users WHERE id=11" 2>/dev/null | tr -dc '0-9')"
chk "id=10 present in shard 0 (sql1)"          "1" "$d0"
chk "id=11 present in shard 1 (sql2)"          "1" "$d1"
chk "id=11 absent from shard 0 (no crosstalk)" "0" "$x0"
# Orders co-locate with their owner.
curl -s --max-time 15 -X POST "$BASE/v1/op/create_order" -H "$AUTH" -H "$JSON" -d '{"params":{"user_id":10,"amount":5.0,"status":"paid"}}' >/dev/null
chk "read-back via LB: order count for user 10 == 1" "1" \
    "$(curl -s --max-time 15 -X POST "$BASE/v1/op/count_orders" -H "$AUTH" -H "$JSON" -d '{"params":{"user_id":10}}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["rows"][0]["n"])' 2>/dev/null)"

# ------------------------------------------ 4. stress through the LB ------
say ""
say "== 4. stress through the $LB LB (k6) =="
NET="$(docker inspect sql-stack-nginx sql-stack-haproxy 2>/dev/null | python3 -c 'import json,sys;d=json.load(sys.stdin);print(next(iter(d[0]["NetworkSettings"]["Networks"])))' 2>/dev/null)"
[ -n "$NET" ] || NET="sql-stack_edge"
if docker run --rm --network "$NET" \
    -e BASE="http://${LBSVC}:${LBPORT}" -e TOKEN="$TOKEN" -e VUS=60 -e DURATION=15s \
    -v "$(pwd)/stress":/scripts:ro,Z docker.io/grafana/k6:latest run /scripts/load.js >/tmp/k6.out 2>&1; then
    ok "k6 thresholds passed through LB (errors<1%, p95<500ms)"
else
    bad "k6 thresholds failed through LB"; grep -iE "✗|threshold|error rate" /tmp/k6.out | head -4 | sed 's/^/       /'
fi
reqs="$(grep -E 'http_reqs' /tmp/k6.out | head -1 | tr -s ' ')"
[ -n "$reqs" ] && say "     $reqs"

# ---------------------------------------------------------------- report --
say ""
TOTAL=$((PASS+FAIL))
if [ "$FAIL" -eq 0 ]; then say "== FINAL UAT PASSED ($LB): $PASS/$TOTAL"; RC=0
else say "== FINAL UAT FAILED ($LB): $FAIL of $TOTAL"; RC=1; fi
say "   see uat/REPORT.md for the full results write-up + scaling analysis"

if [ -z "$KEEP" ]; then $COMPOSE --profile "$PROFILE" down >/dev/null 2>&1; say "-- torn down (use --keep to leave running)"
else say "-- left running on $BASE (--keep)"; fi
exit "$RC"
