#!/bin/sh
# UAT / smoke test for the Gitea SSO stack: builds the stack over TLS,
# proves tinyauth gates the web UI, completes a real login that Gitea's
# reverse proxy authentication turns into a signed-in account, and checks
# that the git/API bypass routes carry no forgeable identity.
#
#   ./run-uat.sh [--down]
#
# Browser access needs these names to resolve to 127.0.0.1:
#   127.0.0.1  gitea.localhost sso-gitea.localhost
set -u

cd "$(dirname "$0")"
. ../../ci/sso-uat-lib.sh

STACK=gitea
TLS_PORT=8456
APP_HOST=gitea.localhost
AUTH_HOST=sso-gitea.localhost
NET_SUBNET=172.31.11.0/24
TRAEFIK_IP=172.31.11.10

uat_env_extra() {
    echo "GITEA_SECRET_KEY=$(openssl rand -base64 32 | tr -d '/+=')"
}

if [ "${1:-}" = "--down" ]; then
    uat_down
    exit 0
fi

say "== Gitea SSO UAT (TLS + tinyauth forwardAuth + reverse-proxy sign-in)"
uat_init

say "-- stage 1: database"
up postgres || exit 1
ensure_running postgres-gitea-sso
wait_healthy postgres-gitea-sso 120 || exit 1

say "-- stage 2: gateway"
up tinyauth traefik || exit 1
ensure_running tinyauth-gitea-sso
ensure_running traefik-gitea-sso
wait_http "$LOGIN/" 90 '^(200|302|307)$' --cacert "$CA" || {
    $RUNTIME logs --tail 20 tinyauth-gitea-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "-- stage 3: gitea"
up gitea || exit 1
ensure_running gitea-sso
wait_healthy gitea-sso 180 || {
    $RUNTIME logs --tail 30 gitea-sso 2>&1 | sed 's/^/     /'; exit 1; }

say "== checks"
check_gate

say "-- end-to-end login (browser UA)"
if sso_login; then
    pass "tinyauth login returns a session"
else
    fail "tinyauth login returns a session" "no cookie"
    uat_report; exit 1
fi

# Every request carrying the SSO session reaches Gitea with the Remote-User
# header, which Gitea's reverse proxy authentication signs in and (first
# time) registers. The account's own profile page proves it exists.
check 200 "SSO session loads Gitea dashboard" --cacert "$CA" -A "$UA" \
    -H "Cookie: $SSO_COOKIE" "$APP/"
_prof="$(curl -s --cacert "$CA" -A "$UA" -H "Cookie: $SSO_COOKIE" \
    -o /dev/null -w '%{http_code}' "$APP/$UAT_USER")"
[ "$_prof" = "200" ] \
    && pass "reverse-proxy auto-registered the SSO user" "profile 200" \
    || fail "reverse-proxy auto-registered the SSO user" "profile $_prof"

say "-- machine bypass routes"
# A git-over-HTTP request is served by Gitea (401/404 for a missing private
# repo), NOT bounced to the SSO login — proving the bypass router works.
_git="$(curl -s --cacert "$CA" -o /dev/null -w '%{http_code}' \
    "$APP/$UAT_USER/demo.git/info/refs?service=git-upload-pack")"
case "$_git" in
    307|302) fail "git-over-HTTP bypasses the interactive gate" "redirected $_git" ;;
    *)       pass "git-over-HTTP bypasses the interactive gate" "gitea $_git" ;;
esac

say "-- header spoofing"
# Forged Remote-User without a session: the gate rejects it.
check 401 "forged Remote-User without a session is rejected" \
    --cacert "$CA" -H 'Remote-User: attacker' "$APP/"
# Forged Remote-User on the API bypass route: strip-identity removes it and
# API reverse-proxy auth is off, so Gitea treats the caller as anonymous.
_api="$(curl -s --cacert "$CA" -H 'Remote-User: attacker' \
    -o /dev/null -w '%{http_code}' "$APP/api/v1/user")"
[ "$_api" = "401" ] \
    && pass "forged Remote-User cannot impersonate on API" "$_api" \
    || fail "forged Remote-User cannot impersonate on API" "got $_api want 401"

uat_report
