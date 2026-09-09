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

# Every assertion below counts matches instead of piping into `grep -q`.
#
# `printf '%s' "$events" | grep -q PATTERN` inverts under `set -o pipefail`
# once the payload exceeds the 64 KiB pipe buffer: grep -q exits on the first
# match, printf is killed by SIGPIPE (141), and pipefail makes the pipeline
# 141 even though the match succeeded. A `! ... grep -q` safety assertion then
# reports PASS precisely when the thing it guards against IS present.
#
# grep -c consumes all its input, so no SIGPIPE and no inversion.
count_matches() { # count_matches <pattern>
  printf '%s' "$events" | grep -c -- "$1" || true
}
present() { # present <pattern> -> 0 when the pattern appears
  [ "$(count_matches "$1")" -gt 0 ]
}
absent() {  # absent <pattern> -> 0 when the pattern does not appear
  [ "$(count_matches "$1")" -eq 0 ]
}

# Prove the helpers before trusting them. The bug they replace reported PASS
# on a violation, so a silent regression here would make every safety
# assertion below meaningless.
selftest_helpers() {
  local events saved_pass=$PASS saved_fail=$FAIL ok=0
  # Larger than the 64 KiB pipe buffer, with the match on the FIRST line:
  # exactly the shape that made `grep -q` return SIGPIPE instead of a match.
  events=$(printf 'NEEDLE\n%*s\n' 200000 '' | tr ' ' 'x')
  present 'NEEDLE' || ok=1
  absent  'NEEDLE' && ok=1
  absent  'NOT-PRESENT-ANYWHERE' || ok=1
  present 'NOT-PRESENT-ANYWHERE' && ok=1
  PASS=$saved_pass; FAIL=$saved_fail
  return $ok
}
echo "==> assertion self-test"
if selftest_helpers; then
  echo "    helpers report matches correctly on a >64KiB payload"
else
  echo "FAIL: the assertion helpers are unreliable; every result below would be void"
  exit 2
fi

echo "==> clearing previous output"
# Without this the suite measures the last run's files and passes with the
# stack down.
find output -mindepth 2 -type f \( -name '*.json' -o -name '*.json.tmp' \) -delete 2>/dev/null || true

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
  "$(present '"host":"web01"' && present '"host":"app01"' && present '"host":"auth01"'; echo $?)"
check "access logs parsed (clientip/method/status extracted)" \
  "$(present '"clientip":"10\.'; echo $?)"
check "JSON app events extracted (action field)" \
  "$(present '"action":"order'; echo $?)"
check "debug events dropped (no 'debug' anywhere in output)" \
  "$(absent 'debug'; echo $?)"
check "emails masked" \
  "$(present '<redacted-email>'; echo $?)"
check "no unmasked emails leaked" \
  "$(absent '@example\.com'; echo $?)"
check "events tagged by the pipeline" \
  "$(present '"demo_pipeline":"demo_logs"'; echo $?)"

echo "==> UI"
ui=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:19001/ || true)
check "web UI reachable on 127.0.0.1:19001 (got $ui)" "$([ "$ui" = 200 ] || [ "$ui" = 302 ]; echo $?)"

echo
echo "smoke test: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
