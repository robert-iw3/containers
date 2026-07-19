#!/usr/bin/env bash
# Smoke test for the Weaviate stack: readiness, authentication (admin key
# works, anonymous and bad keys rejected, read-only key cannot write),
# and metrics exposure.
set -euo pipefail

cd "$(dirname "$0")/.."

BASE=http://127.0.0.1:8080/v1

[ -s .env ] || { echo "FAIL: weaviate/.env missing — run ./scripts/bootstrap-env.sh"; exit 1; }
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
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "==> waiting for readiness endpoint"
for i in $(seq 1 60); do
  if curl -sf "$BASE/.well-known/ready" >/dev/null 2>&1; then break; fi
  [ "$i" = 60 ] && { echo "FAIL: /.well-known/ready never responded"; exit 1; }
  sleep 2
done
echo "    ready OK"

echo "==> auth checks"
check "anonymous request rejected" 401 "$(code "$BASE/schema")"
check "bad API key rejected" 401 \
  "$(code -H 'Authorization: Bearer not-a-real-key' "$BASE/schema")"
check "admin key accepted" 200 \
  "$(code -H "Authorization: Bearer $WEAVIATE_ADMIN_KEY" "$BASE/schema")"
check "readonly key can read schema" 200 \
  "$(code -H "Authorization: Bearer $WEAVIATE_READONLY_KEY" "$BASE/schema")"
check "readonly key cannot create a collection" 403 \
  "$(code -X POST -H "Authorization: Bearer $WEAVIATE_READONLY_KEY" \
     -H 'Content-Type: application/json' -d '{"class":"SmokeDenied"}' "$BASE/schema")"

echo "==> write round-trip with admin key"
check "create collection" 200 \
  "$(code -X POST -H "Authorization: Bearer $WEAVIATE_ADMIN_KEY" \
     -H 'Content-Type: application/json' \
     -d '{"class":"SmokeTest","vectorizer":"none"}' "$BASE/schema")"
check "insert object" 200 \
  "$(code -X POST -H "Authorization: Bearer $WEAVIATE_ADMIN_KEY" \
     -H 'Content-Type: application/json' \
     -d '{"class":"SmokeTest","properties":{"note":"hello"},"vector":[0.1,0.2,0.3]}' \
     "$BASE/objects")"
check "drop collection" 200 \
  "$(code -X DELETE -H "Authorization: Bearer $WEAVIATE_ADMIN_KEY" "$BASE/schema/SmokeTest")"

echo "==> metrics"
check "prometheus metrics exposed on localhost" 200 \
  "$(code http://127.0.0.1:2112/metrics)"

echo
echo "smoke test: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
