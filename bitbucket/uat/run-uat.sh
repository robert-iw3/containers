#!/bin/sh
# UAT / smoke test for the Bitbucket SSO stack: builds the stack over TLS,
# proves tinyauth gates the web UI, completes a real SSO login through to
# Bitbucket, and confirms the terminal state — the licensed setup wizard —
# is reached. Without an Atlassian licence that wizard is as far as the
# product goes; the REST bypass route is verified alongside.
#
#   ./run-uat.sh [--down]
#
# Browser access needs these names to resolve to 127.0.0.1:
#   127.0.0.1  bitbucket.localhost sso-bitbucket.localhost
#
# Bitbucket boots a JVM; reaching the setup wizard takes a few minutes.
set -u

cd "$(dirname "$0")"
. ../../ci/sso-uat-lib.sh

STACK=bitbucket
TLS_PORT=8461
APP_HOST=bitbucket.localhost
AUTH_HOST=sso-bitbucket.localhost
NET_SUBNET=172.31.16.0/24
TRAEFIK_IP=172.31.16.10

uat_env_extra() {
    echo "BITBUCKET_JVM_MINIMUM_MEMORY=1024m"
    echo "BITBUCKET_JVM_MAXIMUM_MEMORY=2048m"
}

if [ "${1:-}" = "--down" ]; then
    uat_down
    exit 0
fi

say "== Bitbucket SSO UAT (TLS + tinyauth gate; setup wizard is terminal)"
uat_init

say "-- stage 1: database"
up postgres || exit 1
ensure_running postgres-bitbucket-sso
wait_healthy postgres-bitbucket-sso 120 || exit 1

say "-- stage 2: gateway"
up tinyauth traefik || exit 1
ensure_running tinyauth-bitbucket-sso
ensure_running traefik-bitbucket-sso
wait_http "$LOGIN/" 90 '^(200|302|307)$' --cacert "$CA" -A "$UA" || {
    $RUNTIME logs --tail 20 tinyauth-bitbucket-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "-- stage 3: bitbucket (JVM boot to setup wizard, this is slow)"
up bitbucket || exit 1
ensure_running bitbucket-sso
wait_healthy bitbucket-sso 600 || {
    $RUNTIME logs --tail 40 bitbucket-sso 2>&1 | sed 's/^/     /'; exit 1; }

# FIRST_RUN is reported a little before the setup web app is mapped; poll the
# app root until it stops 404ing so the assertions see the real wizard.
say "-- waiting for the setup web app to map"
_i=0
while [ "$_i" -lt 180 ]; do
    _c="$($RUNTIME exec bitbucket-sso curl -s -o /dev/null -w '%{http_code}' \
        http://localhost:7990/ 2>/dev/null)"
    case "$_c" in 200|302) break ;; esac
    _i=$((_i + 3)); sleep 3
done

say "== checks"
check_gate

say "-- end-to-end login (browser UA)"
if sso_login; then
    pass "tinyauth login returns a session"
else
    fail "tinyauth login returns a session" "no cookie"
    uat_report; exit 1
fi

# With the SSO session the gate lets the browser through to Bitbucket, which
# on an unlicensed instance serves its setup wizard. Reaching that wizard is
# the terminal state this deployment targets.
_setup="$(curl -s -L --cacert "$CA" -A "$UA" -H "Cookie: $SSO_COOKIE" "$APP/")"
if printf '%s' "$_setup" | grep -qiE 'setup|licen[sc]e'; then
    pass "SSO session reaches the Bitbucket setup wizard"
else
    fail "SSO session reaches the Bitbucket setup wizard" "no setup marker"
fi
check 200 "setup wizard served over TLS behind the gate" -L --cacert "$CA" \
    -A "$UA" -H "Cookie: $SSO_COOKIE" "$APP/setup"

say "-- REST bypass (not gated)"
# The public application-properties endpoint answers on /rest without the
# SSO gate — a REST/CI client reaches Bitbucket directly.
_rest="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 --cacert "$CA" \
    "$APP/rest/api/1.0/application-properties")"
case "$_rest" in
    30[27]) fail "REST API bypasses the interactive gate" "gated ($_rest)" ;;
    *)      pass "REST API bypasses the interactive gate" "bitbucket $_rest" ;;
esac

say "-- header spoofing"
check 401 "forged Remote-User without a session is rejected" \
    --cacert "$CA" -H 'Remote-User: attacker' "$APP/"

uat_report
