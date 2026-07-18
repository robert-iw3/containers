#!/bin/sh
# UAT battery for the API Firewall.
#
#   ./run-uat.sh [--keep]
#
# Brings up the UAT stack (firewall + FastAPI mock backend), exports the
# backend's live OpenAPI spec for the firewall, then runs a battery of
# positive and negative cases. In this stack every firewall block returns
# HTTP 418, so a 418 always proves the firewall acted and any other status
# came from the app. The backend records every request it receives; after
# the negative phase the battery asserts none of the blocked requests ever
# reached it.
#
# Exit code 0 iff every case passes. --keep leaves the stack running.
set -u

cd "$(dirname "$0")"

COMPOSE="docker compose -f docker-compose.uat.yml"
BASE=http://127.0.0.1:8081
KEEP="${1:-}"

PASS=0
FAIL=0

say() { printf '%s\n' "$*"; }

check() { # check <expected_code> <description> [curl args...]
    _want="$1"; _desc="$2"; shift 2
    _got="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@")"
    if [ "$_got" = "$_want" ]; then
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "$_desc" "$_got"
    else
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s got %s want %s\n' "$_desc" "$_got" "$_want"
    fi
}

check_num() { # check_num <expected> <description> <actual>
    if [ "$3" = "$1" ]; then
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "$2" "$3"
    else
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s got %s want %s\n' "$2" "$3" "$1"
    fi
}

backend_hits() {
    docker exec apifw-uat-backend python3 -c \
        'import json,urllib.request; print(json.load(urllib.request.urlopen("http://127.0.0.1:8000/_uat/hits"))["count"])'
}

wait_healthy() { # wait_healthy <container> <seconds>
    _i=0
    while [ "$_i" -lt "$2" ]; do
        if [ "$(docker inspect --format '{{.State.Health.Status}}' "$1" 2>/dev/null)" = "healthy" ]; then
            return 0
        fi
        _i=$((_i + 1)); sleep 1
    done
    say "!! $1 not healthy after $2 s"
    docker logs --tail 10 "$1" 2>&1 | sed 's/^/     /'
    return 1
}

# ---------------------------------------------------------------- setup --
say "== UAT setup"

if [ ! -f ../crs/crs-setup.conf ]; then
    say "-- OWASP CRS missing; fetching..."
    ../get-crs.sh || exit 1
fi

# The spec file must exist before the firewall container is created.
[ -f openapi.json ] || echo '{}' > openapi.json

say "-- starting mock backend..."
$COMPOSE up -d --build uat-backend >/dev/null 2>&1 || { $COMPOSE up -d --build uat-backend; exit 1; }
wait_healthy apifw-uat-backend 60 || exit 1

say "-- exporting the backend's live OpenAPI spec..."
docker exec apifw-uat-backend python3 export_spec.py > openapi.json.new || exit 1
if ! cmp -s openapi.json openapi.json.new; then
    mv openapi.json.new openapi.json
    say "   spec refreshed from the app"
    # podman-compose `rm -sf` is unreliable; remove with the engine directly
    # so the firewall is recreated against the new spec.
    docker rm -f apifw-uat-firewall >/dev/null 2>&1
else
    rm -f openapi.json.new
fi

say "-- starting firewall..."
$COMPOSE up -d --build api-firewall >/dev/null 2>&1 || { $COMPOSE up -d --build api-firewall; exit 1; }
wait_healthy apifw-uat-firewall 60 || exit 1

docker exec apifw-uat-backend python3 -c \
    'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/_uat/reset", data=b"")' >/dev/null

# ------------------------------------------------- positive: must pass --
say ""
say "== Positive cases (proxied to the app)"
check 200 "GET  /health" "$BASE/health"
check 200 "GET  /items?limit=10" "$BASE/items?limit=10"
check 200 "GET  /items/1" "$BASE/items/1"
check 404 "GET  /items/999 (documented 404 passes)" "$BASE/items/999"
check 201 "POST /items (valid body)" -X POST "$BASE/items" \
    -H 'Content-Type: application/json' -d '{"name":"uat-widget","price":4.2,"tags":["uat"]}'
check 200 "PUT  /items/1 (valid body)" -X PUT "$BASE/items/1" \
    -H 'Content-Type: application/json' -d '{"name":"anvil-v2","price":19.99}'
check 204 "DELETE /items/2" -X DELETE "$BASE/items/2"
check 200 "GET  /admin/secrets (valid API key)" "$BASE/admin/secrets" \
    -H 'X-API-Key: uat-valid-key'

HITS_BEFORE="$(backend_hits)"

# ------------------------------------- negative: firewall must block ----
say ""
say "== Negative cases (418 = blocked by the firewall)"

say "-- OpenAPI schema violations"
check 418 "GET  /items?limit=abc (type)" "$BASE/items?limit=abc"
check 418 "GET  /items?limit=1000 (max 100)" "$BASE/items?limit=1000"
check 418 "GET  /items/0 (min 1)" "$BASE/items/0"
check 418 "GET  /items/abc (type)" "$BASE/items/abc"
check 418 "POST /items {} (missing required)" -X POST "$BASE/items" \
    -H 'Content-Type: application/json' -d '{}'
check 418 "POST /items price<=0 (constraint)" -X POST "$BASE/items" \
    -H 'Content-Type: application/json' -d '{"name":"x","price":-5}'
check 418 "POST /items unknown field (additionalProperties)" -X POST "$BASE/items" \
    -H 'Content-Type: application/json' -d '{"name":"x","price":1,"hack":true}'
# application/xml is allowed by the CRS content-type policy but not
# declared in the spec, so this block must come from schema validation.
check 418 "POST /items application/xml (undeclared content type)" -X POST "$BASE/items" \
    -H 'Content-Type: application/xml' -d '<item/>'

say "-- unknown surface (shadow API stays hidden)"
check 418 "GET  /unknown (path not in spec)" "$BASE/unknown"
check 418 "PATCH /items/1 (method not in spec)" -X PATCH "$BASE/items/1" \
    -H 'Content-Type: application/json' -d '{"name":"x","price":1}'
check 418 "GET  /_uat/hits (hidden endpoint unreachable)" "$BASE/_uat/hits"

say "-- authn enforcement"
check 418 "GET  /admin/secrets (missing required API key)" "$BASE/admin/secrets"
check 418 "GET  /admin/secrets (denylisted token)" "$BASE/admin/secrets" \
    -H 'X-API-Key: revoked-uat-token'

say "-- WAF layer (Coraza + OWASP CRS)"
check 403 "GET  /items?limit=1 (sqlmap UA, CRS 913100)" -A 'sqlmap/1.7' "$BASE/items?limit=1"
check 403 "POST /items XSS payload in valid field (CRS 941xxx)" -X POST "$BASE/items" \
    -H 'Content-Type: application/json' \
    -d '{"name":"<script>alert(document.cookie)</script>","price":1}'

check_num "$HITS_BEFORE" "backend hit count unchanged (blocks never proxied)" "$(backend_hits)"

say "-- response validation"
check 418 "GET  /rogue (app response violates spec)" "$BASE/rogue"

# ---------------------------------------------------------------- report --
say ""
TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
    say "== UAT PASSED: $PASS/$TOTAL cases"
    RC=0
else
    say "== UAT FAILED: $FAIL of $TOTAL cases failed"
    RC=1
fi

if [ "$KEEP" != "--keep" ]; then
    $COMPOSE down >/dev/null 2>&1
    say "-- stack torn down (use --keep to leave it running)"
else
    say "-- stack left running on $BASE (--keep)"
fi

exit "$RC"
