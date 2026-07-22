#!/bin/sh
# UAT / smoke test for the Grafana SSO stack: builds the stack over TLS,
# proves tinyauth gates it, and completes a real login through to an
# authenticated Grafana session created from the SSO identity.
#
#   ./run-uat.sh [--down]
#
# Browser access needs these names to resolve to 127.0.0.1 (most systems
# already resolve *.localhost):
#   127.0.0.1  grafana.localhost sso-grafana.localhost
set -u

cd "$(dirname "$0")"
. ../../ci/sso-uat-lib.sh

STACK=grafana
TLS_PORT=8455
APP_HOST=grafana.localhost
AUTH_HOST=sso-grafana.localhost
NET_SUBNET=172.31.10.0/24
TRAEFIK_IP=172.31.10.10

uat_env_extra() {
    echo "GRAFANA_DEFAULT_ROLE=Editor"
}

if [ "${1:-}" = "--down" ]; then
    uat_down
    exit 0
fi

say "== Grafana SSO UAT (TLS + tinyauth forwardAuth + header sign-in)"
uat_init

say "-- stage 1: database"
up postgres || exit 1
ensure_running postgres-grafana-sso
wait_healthy postgres-grafana-sso 120 || exit 1

say "-- stage 2: gateway"
up tinyauth traefik || exit 1
ensure_running tinyauth-grafana-sso
ensure_running traefik-grafana-sso
wait_http "$LOGIN/" 90 '^(200|302|307)$' --cacert "$CA" || {
    $RUNTIME logs --tail 20 tinyauth-grafana-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "-- stage 3: grafana"
up grafana || exit 1
ensure_running grafana-sso
wait_healthy grafana-sso 180 || {
    $RUNTIME logs --tail 30 grafana-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "== checks"
check_gate

# Log in against tinyauth and reuse the session for the application.
say "-- end-to-end login (browser UA)"
if sso_login; then
    pass "tinyauth login returns a session"
else
    fail "tinyauth login returns a session" "no cookie"
    uat_report; exit 1
fi

# Grafana signs the user in from the header traefik copied off the
# decision, so an authenticated request identifies the SSO user without a
# second login. This is the build -> login assertion.
_who="$(curl -s --cacert "$CA" -A "$UA" -H "Cookie: $SSO_COOKIE" "$APP/api/user")"
if [ "$(printf '%s' "$_who" | jq -r '.login // empty')" = "$UAT_USER" ]; then
    pass "SSO session signs in to Grafana" "$(printf '%s' "$_who" | jq -r '.login')"
else
    fail "SSO session signs in to Grafana" "$(printf '%s' "$_who" | head -c 120)"
fi

# The home dashboard renders for that same session.
check 200 "authenticated user loads Grafana UI" --cacert "$CA" -A "$UA" \
    -H "Cookie: $SSO_COOKIE" "$APP/"

say "-- header spoofing"
# Unauthenticated, carrying a forged identity: the gate rejects it before
# Grafana is reached.
check 401 "forged Remote-User without a session is rejected" \
    --cacert "$CA" -H 'Remote-User: attacker' "$APP/api/user"

# Authenticated, carrying a forged identity: traefik replaces the header
# with the decision's value, so the session's own user is who Grafana sees.
_spoof="$(curl -s --cacert "$CA" -A "$UA" -H "Cookie: $SSO_COOKIE" \
    -H 'Remote-User: attacker' "$APP/api/user" | jq -r '.login // empty')"
if [ "$_spoof" = "$UAT_USER" ]; then
    pass "forged Remote-User cannot impersonate" "stayed $_spoof"
else
    fail "forged Remote-User cannot impersonate" "became ${_spoof:-unknown}"
fi

# The token bypass router carries no identity either: it reaches Grafana,
# which rejects the bogus token on its own.
check 401 "token route rejects an invalid bearer token" --cacert "$CA" \
    -H 'Authorization: Bearer not-a-real-token' "$APP/api/org"

_tok="$(curl -s --cacert "$CA" -H 'Authorization: Bearer not-a-real-token' \
    -H 'Remote-User: attacker' "$APP/api/user" -o /dev/null -w '%{http_code}')"
[ "$_tok" = "401" ] \
    && pass "token route strips forged identity header" "$_tok" \
    || fail "token route strips forged identity header" "got $_tok want 401"

uat_report
