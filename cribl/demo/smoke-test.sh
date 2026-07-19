#!/usr/bin/env bash
# Smoke / UAT test for the Cribl log demo: brings the demo up, waits for
# events to flow generator -> syslog -> pipeline -> filesystem, then
# asserts the pipeline actually did its job (parsing, dropping, masking).
set -euo pipefail

cd "$(dirname "$0")"

RUNTIME="${RUNTIME:-podman}"
COMPOSE="${COMPOSE:-podman-compose}"

PASS=0
FAIL=0
check() { # check <description> <ok(0/1)> [detail]
  if [ "$2" = 0 ]; then
    PASS=$((PASS + 1)); printf '  PASS  %s\n' "$1"
  else
    FAIL=$((FAIL + 1)); printf '  FAIL  %s%s\n' "$1" "${3:+ ($3)}"
  fi
}

echo "==> starting demo stack"
$COMPOSE -f docker-compose.demo.yml up -d >/dev/null 2>&1 || $COMPOSE -f docker-compose.demo.yml up -d

echo "==> waiting for cribl health"
for i in $(seq 1 45); do
  if [ "$("$RUNTIME" inspect --format '{{.State.Health.Status}}' cribl-demo 2>/dev/null)" = "healthy" ]; then
    break
  fi
  [ "$i" = 45 ] && { echo "FAIL: cribl-demo never became healthy"; exit 1; }
  sleep 2
done
echo "    healthy"

echo "==> waiting for processed events in ./output"
collect() {
  find output -mindepth 2 -type f \( -name '*.json' -o -name '*.json.tmp' \) \
    -exec cat {} + 2>/dev/null || true
}
events=""
for i in $(seq 1 45); do
  events=$(collect)
  [ -n "$events" ] && [ "$(printf '%s\n' "$events" | wc -l)" -ge 50 ] && break
  sleep 2
done
count=$(printf '%s\n' "$events" | grep -c . || true)
check "events reached the filesystem destination (${count} events)" \
  "$([ "$count" -ge 50 ]; echo $?)"

echo "==> pipeline behaviour"
check "web + app + auth hosts all present" \
  "$(printf '%s' "$events" | grep -q '"host":"web01"' \
     && printf '%s' "$events" | grep -q '"host":"app01"' \
     && printf '%s' "$events" | grep -q '"host":"auth01"'; echo $?)"
check "access logs parsed (clientip/method/status extracted)" \
  "$(printf '%s' "$events" | grep -q '"clientip":"10\.' ; echo $?)"
check "JSON app events extracted (action field)" \
  "$(printf '%s' "$events" | grep -q '"action":"order' ; echo $?)"
check "debug events dropped (no 'debug' anywhere in output)" \
  "$(! printf '%s' "$events" | grep -q 'debug'; echo $?)"
check "emails masked" \
  "$(printf '%s' "$events" | grep -q '<redacted-email>'; echo $?)"
check "no unmasked emails leaked" \
  "$(! printf '%s' "$events" | grep -q '@example\.com'; echo $?)"
check "events tagged by the pipeline" \
  "$(printf '%s' "$events" | grep -q '"demo_pipeline":"demo_logs"'; echo $?)"

echo "==> UI"
ui=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:19001/ || true)
check "web UI reachable on 127.0.0.1:19001 (got $ui)" "$([ "$ui" = 200 ] || [ "$ui" = 302 ]; echo $?)"

echo
echo "smoke test: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
