#!/bin/sh
# End-to-end smoke test for the firewall -> API -> sharded SQL stack.
#
#   ./smoke-test.sh [--keep]
#
# Builds the images, exports the API's live OpenAPI spec for the firewall,
# starts the stack in dependency order, then verifies: CRUD through the
# firewall, shard distribution, block behaviour (schema/auth/WAF), and that
# the data really landed in SQL Server. Exit 0 iff everything passes.
set -u

cd "$(dirname "$0")"

COMPOSE="docker compose -f docker-compose.yml"
BASE=http://127.0.0.1:8082
KEY="${SQL_API_KEYS:-demo-key-1}"
KEEP="${1:-}"

PASS=0
FAIL=0

say() { printf '%s\n' "$*"; }

check() { # check <expected_code> <description> [curl args...]
    _want="$1"; _desc="$2"; shift 2
    _got="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@")"
    if [ "$_got" = "$_want" ]; then
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "$_desc" "$_got"
    else
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s got %s want %s\n' "$_desc" "$_got" "$_want"
    fi
}

check_eq() { # check_eq <expected> <description> <actual>
    if [ "$3" = "$1" ]; then
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "$2" "$3"
    else
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s got %s want %s\n' "$2" "$3" "$1"
    fi
}

wait_healthy() { # wait_healthy <container> <seconds>
    _i=0
    while [ "$_i" -lt "$2" ]; do
        if [ "$(docker inspect --format '{{.State.Health.Status}}' "$1" 2>/dev/null)" = "healthy" ]; then
            return 0
        fi
        _i=$((_i + 1)); sleep 2
    done
    say "!! $1 not healthy after $(($2 * 2)) s"
    docker logs --tail 12 "$1" 2>&1 | sed 's/^/     /'
    return 1
}

# ---------------------------------------------------------------- setup --
say "== setup"

if [ ! -f ../../crs/crs-setup.conf ]; then
    say "-- OWASP CRS missing; fetching..."
    ../../get-crs.sh || exit 1
fi

say "-- building API image + exporting its OpenAPI spec..."
$COMPOSE build api >/dev/null 2>&1 || { $COMPOSE build api; exit 1; }
docker run --rm localhost/apifw-sql-api:latest python3 export_spec.py > openapi.json || exit 1

say "-- starting SQL shards (cold start takes ~1 min)..."
$COMPOSE up -d sql1 sql2 >/dev/null 2>&1 || { $COMPOSE up -d sql1 sql2; exit 1; }
wait_healthy apifw-sql-shard1 90 || exit 1
wait_healthy apifw-sql-shard2 90 || exit 1

say "-- starting API tier..."
$COMPOSE up -d api >/dev/null 2>&1 || { $COMPOSE up -d api; exit 1; }
api_ctr="$(docker ps --format '{{.Names}}' | grep -E 'api[-_]1$|_api_1$' | head -1)"
[ -n "$api_ctr" ] || api_ctr="$(docker ps --format '{{.Names}}' | grep -E 'apifw-sql.*api' | head -1)"
wait_healthy "$api_ctr" 60 || exit 1

say "-- starting firewall..."
$COMPOSE up -d --build api-firewall >/dev/null 2>&1 || { $COMPOSE up -d --build api-firewall; exit 1; }
wait_healthy apifw-sql-firewall 60 || exit 1

# ------------------------------------------------------------- positive --
say ""
say "== Positive cases (through the firewall, into SQL)"
check 200 "GET  /health" "$BASE/health"

r1="$(curl -s --max-time 15 -X POST "$BASE/v1/owners/1/records" \
    -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
    -d '{"kind":"task","data":{"title":"ship it","done":false}}')"
r2="$(curl -s --max-time 15 -X POST "$BASE/v1/owners/2/records" \
    -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
    -d '{"kind":"event","data":{"type":"login","ip":"10.0.0.5"}}')"
id1="$(printf '%s' "$r1" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("id",""))' 2>/dev/null)"
shard1="$(printf '%s' "$r1" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("shard",""))' 2>/dev/null)"
shard2="$(printf '%s' "$r2" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("shard",""))' 2>/dev/null)"

check_eq "1" "POST owner 1 record -> shard 1" "$shard1"
check_eq "0" "POST owner 2 record -> shard 0 (distribution works)" "$shard2"
check 200 "GET  the created record" -H "X-API-Key: $KEY" "$BASE/v1/owners/1/records/$id1"
check 200 "GET  list filtered by kind" -H "X-API-Key: $KEY" "$BASE/v1/owners/1/records?kind=task"
check 200 "PUT  update the record" -X PUT "$BASE/v1/owners/1/records/$id1" \
    -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
    -d '{"kind":"task","data":{"title":"ship it","done":true}}'
check 404 "GET  missing record (documented 404)" -H "X-API-Key: $KEY" "$BASE/v1/owners/1/records/999999"
check 200 "GET  /v1/shards (both healthy)" -H "X-API-Key: $KEY" "$BASE/v1/shards"

healthy_shards="$(curl -s --max-time 15 -H "X-API-Key: $KEY" "$BASE/v1/shards" \
    | python3 -c 'import json,sys; print(sum(1 for s in json.load(sys.stdin) if s["healthy"]))' 2>/dev/null)"
check_eq "2" "shard health reported healthy on both" "$healthy_shards"

# ------------------------------------------------------------- negative --
say ""
say "== Negative cases (403 = blocked by the firewall)"
check 403 "GET  /v1/owners/1/records without API key" "$BASE/v1/owners/1/records"
check 403 "GET  owner id wrong type" -H "X-API-Key: $KEY" "$BASE/v1/owners/abc/records"
check 403 "GET  limit above maximum" -H "X-API-Key: $KEY" "$BASE/v1/owners/1/records?limit=9999"
check 403 "POST kind violates pattern (SQLi shaped)" -X POST "$BASE/v1/owners/1/records" \
    -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
    -d '{"kind":"x UNION SELECT","data":{}}'
check 403 "POST unknown body field" -X POST "$BASE/v1/owners/1/records" \
    -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
    -d '{"kind":"task","data":{},"admin":true}'
check 403 "GET  unknown path" "$BASE/admin/backdoor"
check 403 "GET  scanner UA (WAF/CRS)" -A 'sqlmap/1.7' -H "X-API-Key: $KEY" "$BASE/health"

# ---------------------------------------------------- data really in SQL --
say ""
say "== Persistence (rows visible inside the shards)"
n1="$(docker exec apifw-sql-shard1 /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa \
    -P "${SQL_SA_PASSWORD:-ApiFw_Str0ng!Pass}" -d records -h -1 -W \
    -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.records" 2>/dev/null | tr -dc '0-9')"
n2="$(docker exec apifw-sql-shard2 /opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa \
    -P "${SQL_SA_PASSWORD:-ApiFw_Str0ng!Pass}" -d records -h -1 -W \
    -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.records" 2>/dev/null | tr -dc '0-9')"
[ -n "$n1" ] && [ "$n1" -ge 1 ] 2>/dev/null \
    && { PASS=$((PASS+1)); printf '  PASS  %-58s %s\n' "shard 1 row count >= 1" "$n1"; } \
    || { FAIL=$((FAIL+1)); printf '  FAIL  %-58s got %s\n' "shard 1 row count >= 1" "${n1:-none}"; }
[ -n "$n2" ] && [ "$n2" -ge 1 ] 2>/dev/null \
    && { PASS=$((PASS+1)); printf '  PASS  %-58s %s\n' "shard 2 row count >= 1" "$n2"; } \
    || { FAIL=$((FAIL+1)); printf '  FAIL  %-58s got %s\n' "shard 2 row count >= 1" "${n2:-none}"; }

check 204 "DELETE the record (cleanup path works)" -X DELETE \
    -H "X-API-Key: $KEY" "$BASE/v1/owners/1/records/$id1"

# ---------------------------------------------------------------- report --
say ""
TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
    say "== SMOKE TEST PASSED: $PASS/$TOTAL"
    RC=0
else
    say "== SMOKE TEST FAILED: $FAIL of $TOTAL"
    RC=1
fi

if [ "$KEEP" != "--keep" ]; then
    $COMPOSE down >/dev/null 2>&1
    say "-- stack torn down (use --keep to leave it running)"
else
    say "-- stack left running on $BASE (--keep)"
fi

exit "$RC"
