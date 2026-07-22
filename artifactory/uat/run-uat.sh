#!/bin/sh
# UAT / smoke test for the Artifactory SSO stack: builds the stack over TLS,
# proves tinyauth gates the web UI, completes a real SSO login through to
# the Artifactory app, and confirms the registry/API paths answer without
# the interactive gate.
#
#   ./run-uat.sh [--down]
#
# Browser access needs these names to resolve to 127.0.0.1:
#   127.0.0.1  artifactory.localhost sso-artifactory.localhost
#
# Artifactory boots a JVM plus several microservices; allow several minutes.
set -u

cd "$(dirname "$0")"
. ../../ci/sso-uat-lib.sh

STACK=artifactory
TLS_PORT=8459
APP_HOST=artifactory.localhost
AUTH_HOST=sso-artifactory.localhost
NET_SUBNET=172.31.14.0/24
TRAEFIK_IP=172.31.14.10

if [ "${1:-}" = "--down" ]; then
    uat_down
    exit 0
fi

say "== Artifactory SSO UAT (TLS + tinyauth gate; native auth retained)"
uat_init

say "-- stage 1: database"
up postgres || exit 1
ensure_running postgres-artifactory-sso
wait_healthy postgres-artifactory-sso 120 || exit 1

say "-- stage 2: gateway"
up tinyauth traefik || exit 1
ensure_running tinyauth-artifactory-sso
ensure_running traefik-artifactory-sso
wait_http "$LOGIN/" 90 '^(200|302|307)$' --cacert "$CA" || {
    $RUNTIME logs --tail 20 tinyauth-artifactory-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "-- stage 3: artifactory (JVM + microservices, this is slow)"
up artifactory || exit 1
ensure_running artifactory-sso
wait_healthy artifactory-sso 600 || {
    $RUNTIME logs --tail 40 artifactory-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "== checks"
# UI path assertions (the machine paths have their own routers, so probe /).
check 401 "UI rejects unauthenticated API request" --cacert "$CA" "$APP/"
check 307 "UI redirects browser to SSO login"       --cacert "$CA" -A "$UA" -H 'Accept: text/html' "$APP/"
check 200 "tinyauth login UI over TLS"             -L --cacert "$CA" -A "$UA" "$LOGIN/"
_loc="$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 30 --cacert "$CA" \
    -A "$UA" -H 'Accept: text/html' "$APP/")"
case "$_loc" in
    *"$AUTH_HOST:$TLS_PORT/login"*redirect_uri*)
        pass "redirect targets login UI with return URL" ;;
    *)  fail "redirect targets login UI with return URL" "$_loc" ;;
esac

say "-- end-to-end login (browser UA)"
if sso_login; then
    pass "tinyauth login returns a session"
else
    fail "tinyauth login returns a session" "no cookie"
    uat_report; exit 1
fi

# With the SSO session the gate lets the request through to Artifactory's
# own UI. This is the build -> login assertion.
check 200 "SSO session reaches the Artifactory UI" -L --cacert "$CA" -A "$UA" \
    -H "Cookie: $SSO_COOKIE" "$APP/ui/"

say "-- registry / API bypass (not gated)"
# The public system ping answers on the API path with no SSO gate — a CI or
# registry client reaches Artifactory directly.
check 200 "REST API ping bypasses the interactive gate" \
    --cacert "$CA" "$APP/artifactory/api/system/ping"
# The docker registry v2 base requires Artifactory credentials: reachable
# without the SSO gate (401 from Artifactory, not a 307 to the login UI).
_v2="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 --cacert "$CA" "$APP/v2/")"
case "$_v2" in
    30[27]) fail "docker registry v2 bypasses the interactive gate" "gated ($_v2)" ;;
    *)      pass "docker registry v2 bypasses the interactive gate" "artifactory $_v2" ;;
esac

say "-- header spoofing"
check 401 "forged Remote-User without a session is rejected" \
    --cacert "$CA" -H 'Remote-User: attacker' "$APP/"

uat_report
