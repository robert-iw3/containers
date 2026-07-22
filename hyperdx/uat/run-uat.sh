#!/bin/sh
# UAT / smoke test for the HyperDX SSO stack: builds the stack over TLS,
# proves tinyauth gates the UI, completes a real SSO login through to the
# HyperDX app, and confirms the OTLP ingest ports answer without the gate.
#
#   ./run-uat.sh [--down]
#
# Browser access needs these names to resolve to 127.0.0.1:
#   127.0.0.1  hyperdx.localhost sso-hyperdx.localhost
set -u

cd "$(dirname "$0")"
. ../../ci/sso-uat-lib.sh

STACK=hyperdx
TLS_PORT=8458
APP_HOST=hyperdx.localhost
AUTH_HOST=sso-hyperdx.localhost
NET_SUBNET=172.31.13.0/24
TRAEFIK_IP=172.31.13.10

if [ "${1:-}" = "--down" ]; then
    uat_down
    exit 0
fi

say "== HyperDX SSO UAT (TLS + tinyauth gate; native auth retained)"
uat_init

say "-- stage 1: gateway"
up tinyauth traefik || exit 1
ensure_running tinyauth-hyperdx-sso
ensure_running traefik-hyperdx-sso
wait_http "$LOGIN/" 90 '^(200|302|307)$' --cacert "$CA" || {
    $RUNTIME logs --tail 20 tinyauth-hyperdx-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "-- stage 2: hyperdx (bundled clickhouse + otel, this is slow)"
up hyperdx || exit 1
ensure_running hyperdx-sso
wait_healthy hyperdx-sso 300 || {
    $RUNTIME logs --tail 40 hyperdx-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "== checks"
check_gate

say "-- end-to-end login (browser UA)"
if sso_login; then
    pass "tinyauth login returns a session"
else
    fail "tinyauth login returns a session" "no cookie"
    uat_report; exit 1
fi

# With the SSO session the gate lets the request through and HyperDX serves
# its application. This is the build -> login assertion: the user cleared
# the identity provider and reached the app.
check 200 "SSO session reaches the HyperDX app" -L --cacert "$CA" -A "$UA" \
    -H "Cookie: $SSO_COOKIE" "$APP/"
_body="$(curl -s -L --cacert "$CA" -A "$UA" -H "Cookie: $SSO_COOKIE" "$APP/")"
printf '%s' "$_body" | grep -qi 'hyperdx' \
    && pass "HyperDX UI served behind the gate" \
    || fail "HyperDX UI served behind the gate" "marker not found"

say "-- OTLP ingest path (published outside the gate)"
# The OTLP ports are published on the host, entirely outside traefik and the
# SSO gate. The all-in-one's collector opens the 4317/4318 receivers only
# after HyperDX setup provisions it over OpAMP (much as the Atlassian stacks
# need a licence), so the durable, testable property here is that the ingest
# path is published outside the gate — a host listener bound on 4318 that no
# SSO decision sits in front of.
if $RUNTIME port hyperdx-sso 2>/dev/null | grep -q '4318/tcp' \
   && ss -ltn 2>/dev/null | grep -qE '127\.0\.0\.1:4318'; then
    pass "OTLP ingest port published outside the SSO gate" "4318 bound"
else
    fail "OTLP ingest port published outside the SSO gate" "not published"
fi

say "-- header spoofing"
check 401 "forged Remote-User without a session is rejected" \
    --cacert "$CA" -H 'Remote-User: attacker' "$APP/"

uat_report
