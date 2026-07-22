#!/bin/sh
# UAT / smoke test for the SaltStack SSO stack: builds salt-master, salt-api
# and a minion over TLS, proves tinyauth gates browser access to salt-api,
# and completes a real salt eauth login through to an authenticated API call
# (test.ping against the minion) over the bypass route.
#
#   ./run-uat.sh [--down]
#
# Browser access needs these names to resolve to 127.0.0.1:
#   127.0.0.1  salt.localhost sso-salt.localhost
set -u

cd "$(dirname "$0")"
. ../../ci/sso-uat-lib.sh

STACK=salt
TLS_PORT=8460
APP_HOST=salt.localhost
AUTH_HOST=sso-salt.localhost
NET_SUBNET=172.31.15.0/24
TRAEFIK_IP=172.31.15.10

uat_env_extra() {
    echo "SALT_API_USER=saltapi"
    echo "SALT_SHARED_SECRET=$(openssl rand -hex 20)"
}

if [ "${1:-}" = "--down" ]; then
    uat_down
    exit 0
fi

say "== SaltStack SSO UAT (TLS + tinyauth gate; salt eauth + minion)"
uat_init
SALT_API_USER="$(grep '^SALT_API_USER=' .env | cut -d= -f2)"
SALT_SHARED_SECRET="$(grep '^SALT_SHARED_SECRET=' .env | cut -d= -f2)"

say "-- stage 1: gateway"
up tinyauth traefik || exit 1
ensure_running tinyauth-salt-sso
ensure_running traefik-salt-sso
wait_http "$LOGIN/" 90 '^(200|302|307)$' --cacert "$CA" || {
    $RUNTIME logs --tail 20 tinyauth-salt-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "-- stage 2: build salt 3008 image + start salt-master + salt-api"
$COMPOSE build salt || exit 1
up salt || exit 1
ensure_running salt-sso
wait_healthy salt-sso 180 || {
    $RUNTIME logs --tail 30 salt-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "-- stage 3: minion (auto-accept, then wait for it to register)"
up salt-minion || exit 1
ensure_running salt-minion-sso
_i=0
while [ "$_i" -lt 90 ]; do
    if [ "$($RUNTIME exec salt-sso salt-key -L --out=json 2>/dev/null | jq -r '.minions[]?' | grep -c '^uat-minion$')" -gt 0 ]; then
        break
    fi
    _i=$((_i + 3)); sleep 3
done

say "== checks"
# A browser hitting salt-api without a salt token and without a session is
# gated: tinyauth intercepts before salt-api is reached.
check 307 "salt-api gated for a browser without a token" \
    --cacert "$CA" -A "$UA" -H 'Accept: text/html' "$APP/"
check 200 "tinyauth login UI over TLS" -L --cacert "$CA" -A "$UA" "$LOGIN/"

say "-- end-to-end: SSO session then salt eauth"
if sso_login; then
    pass "tinyauth login returns a session"
else
    fail "tinyauth login returns a session" "no cookie"
    uat_report; exit 1
fi
# With the SSO session, the gated salt-api root is reachable.
check 200 "SSO session reaches salt-api" --cacert "$CA" -A "$UA" \
    -H 'Accept: application/json' -H "Cookie: $SSO_COOKIE" "$APP/"

say "-- salt eauth login (machine bypass) + authenticated call"
# The /login token exchange bypasses the interactive gate and authenticates
# with the sharedsecret eauth (the secret travels in the password field).
TOKEN="$(curl -s --cacert "$CA" -H 'Accept: application/json' -X POST "$APP/login" \
    -d "eauth=sharedsecret&username=$SALT_API_USER&password=$SALT_SHARED_SECRET" \
    | jq -r '.return[0].token // empty')"
if [ -n "$TOKEN" ]; then
    pass "salt-api /login returns an eauth token"
else
    fail "salt-api /login returns an eauth token" "no token"
    $RUNTIME logs --tail 20 salt-sso 2>&1 | sed 's/^/     /'
    uat_report; exit 1
fi

# The authenticated call: run test.ping on the minion through salt-api. A
# true result proves the whole chain — API auth plus the 4505/4506 minion
# transport — is working. This is the build -> authenticated call assertion.
_ping="$(curl -s --cacert "$CA" -H 'Accept: application/json' \
    -H "X-Auth-Token: $TOKEN" -X POST "$APP/" \
    -d 'client=local&tgt=uat-minion&fun=test.ping' \
    | jq -r '.return[0]["uat-minion"] // empty')"
if [ "$_ping" = "true" ]; then
    pass "authenticated test.ping reaches the minion" "true"
else
    fail "authenticated test.ping reaches the minion" "got '${_ping:-none}'"
fi

say "-- minion transport (not gated)"
# The ZeroMQ return port is published directly; a TCP connect proves the
# listener is up outside the HTTP gate.
if python3 -c "import socket,sys; socket.create_connection(('127.0.0.1',4506),5).close()" 2>/dev/null \
   || nc -z -w5 127.0.0.1 4506 2>/dev/null; then
    pass "minion transport port 4506 reachable without the gate"
else
    fail "minion transport port 4506 reachable without the gate" "no connect"
fi

say "-- header spoofing"
check 307 "forged Remote-User without a session is still gated" \
    --cacert "$CA" -A "$UA" -H 'Accept: text/html' -H 'Remote-User: attacker' "$APP/"
# A bogus token on the bypass route is rejected by salt eauth, not honoured.
_bad="$(curl -s --cacert "$CA" -H 'Accept: application/json' \
    -H 'X-Auth-Token: not-a-real-token' \
    -o /dev/null -w '%{http_code}' -X POST "$APP/" \
    -d 'client=local&tgt=*&fun=test.ping')"
case "$_bad" in
    401|403) pass "bogus salt token is rejected on the bypass route" "$_bad" ;;
    *)       fail "bogus salt token is rejected on the bypass route" "got $_bad" ;;
esac

uat_report
