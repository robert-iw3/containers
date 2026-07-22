#!/bin/sh
# UAT / smoke test for the SonarQube SSO stack: builds the stack over TLS,
# proves tinyauth gates the web UI, completes a real login that SonarQube's
# HTTP header SSO turns into a signed-in account, and checks that the token
# bypass route carries no forgeable identity.
#
#   ./run-uat.sh [--down]
#
# Browser access needs these names to resolve to 127.0.0.1:
#   127.0.0.1  sonarqube.localhost sso-sonarqube.localhost
#
# SonarQube boots Elasticsearch and a web server; allow a few minutes.
set -u

cd "$(dirname "$0")"
. ../../ci/sso-uat-lib.sh

STACK=sonar
TLS_PORT=8457
APP_HOST=sonarqube.localhost
AUTH_HOST=sso-sonarqube.localhost
NET_SUBNET=172.31.12.0/24
TRAEFIK_IP=172.31.12.10

if [ "${1:-}" = "--down" ]; then
    uat_down
    exit 0
fi

say "== SonarQube SSO UAT (TLS + tinyauth forwardAuth + header sign-in)"
uat_init

say "-- stage 1: database"
up postgres || exit 1
ensure_running postgres-sonar-sso
wait_healthy postgres-sonar-sso 120 || exit 1

say "-- stage 2: gateway"
up tinyauth traefik || exit 1
ensure_running tinyauth-sonar-sso
ensure_running traefik-sonar-sso
wait_http "$LOGIN/" 90 '^(200|302|307)$' --cacert "$CA" || {
    $RUNTIME logs --tail 20 tinyauth-sonar-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "-- stage 3: sonarqube (Elasticsearch + web, this is slow)"
up sonarqube || exit 1
ensure_running sonarqube-sso
wait_healthy sonarqube-sso 420 || {
    $RUNTIME logs --tail 40 sonarqube-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "== checks"
check_gate

say "-- end-to-end login (browser UA)"
if sso_login; then
    pass "tinyauth login returns a session"
else
    fail "tinyauth login returns a session" "no cookie"
    uat_report; exit 1
fi

# The browser's own /api call is cookie-based (no Authorization header) so
# it stays on the gated route, arriving with Remote-User. SonarQube's header
# SSO signs the user in and returns them from /api/users/current. This is
# the build -> login assertion.
_who="$(curl -s --cacert "$CA" -A "$UA" -H "Cookie: $SSO_COOKIE" "$APP/api/users/current")"
if [ "$(printf '%s' "$_who" | jq -r '.login // empty')" = "$UAT_USER" ]; then
    pass "SSO session signs in to SonarQube" "$(printf '%s' "$_who" | jq -r '.login')"
else
    fail "SSO session signs in to SonarQube" "$(printf '%s' "$_who" | head -c 120)"
fi

check 200 "authenticated user loads SonarQube UI" --cacert "$CA" -A "$UA" \
    -H "Cookie: $SSO_COOKIE" "$APP/"

say "-- header spoofing"
# Forged Remote-User without a session: the gate rejects it.
check 401 "forged Remote-User without a session is rejected" \
    --cacert "$CA" -H 'Remote-User: attacker' "$APP/api/users/current"

# Forged Remote-User with a session: traefik replaces it with the decision
# value, so SonarQube still sees the session's own user.
_spoof="$(curl -s --cacert "$CA" -A "$UA" -H "Cookie: $SSO_COOKIE" \
    -H 'Remote-User: attacker' "$APP/api/users/current" | jq -r '.login // empty')"
[ "$_spoof" = "$UAT_USER" ] \
    && pass "forged Remote-User cannot impersonate" "stayed $_spoof" \
    || fail "forged Remote-User cannot impersonate" "became ${_spoof:-unknown}"

# Token bypass route: a bogus bearer token with a forged identity header is
# stripped of the header and rejected by SonarQube's token check.
_tok="$(curl -s --cacert "$CA" -H 'Authorization: Bearer not-a-real-token' \
    -H 'Remote-User: attacker' -o /dev/null -w '%{http_code}' "$APP/api/users/current")"
[ "$_tok" = "401" ] \
    && pass "token route strips forged identity header" "$_tok" \
    || fail "token route strips forged identity header" "got $_tok want 401"

uat_report
