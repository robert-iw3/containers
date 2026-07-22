#!/bin/sh
# UAT / smoke test for the full SonarQube + Keycloak stack. Brings the whole
# environment up over TLS, then proves build → Keycloak login → SonarQube
# session (created from the Keycloak identity via tinyauth + header SSO).
#
#   ./run-uat.sh [--down]
#
# Needs these names to resolve to 127.0.0.1 (usually automatic for
# *.localhost):
#   127.0.0.1  sonarqube.localhost sso-sonar.localhost keycloak.localhost
#
# Issuer host consistency requires host port 8443 == traefik's :8443.
set -u

cd "$(dirname "$0")"
STACK_DIR="$(cd .. && pwd)"

RUNTIME="${RUNTIME:-podman}"
COMPOSE_BIN="${COMPOSE_BIN:-podman-compose}"
COMPOSE="$COMPOSE_BIN -p sonar-stack --env-file $STACK_DIR/.env -f $STACK_DIR/docker-compose.yml"

TLS_PORT=8443
APP_HOST=sonarqube.localhost
AUTH_HOST=sso-sonar.localhost
KEYCLOAK_HOST=keycloak.localhost
REALM=sonar
NET_SUBNET=172.31.20.0/24
TRAEFIK_IP=172.31.20.10
CA="$STACK_DIR/tls/ca.crt"
APP="https://$APP_HOST:$TLS_PORT"
LOGIN="https://$AUTH_HOST:$TLS_PORT"
ISSUER="https://$KEYCLOAK_HOST:$TLS_PORT/realms/$REALM"
UA="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

PASS=0; FAIL=0
say() { printf '%s\n' "$*"; }
pass() { PASS=$((PASS+1)); printf '  PASS  %-58s %s\n' "$1" "${2:-OK}"; }
fail() { FAIL=$((FAIL+1)); printf '  FAIL  %-58s %s\n' "$1" "${2:-}"; }
check() { _w="$1"; _d="$2"; shift 2; _g="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$@")"; [ "$_g" = "$_w" ] && pass "$_d" "$_g" || fail "$_d" "got $_g want $_w"; }
wait_http() { _u="$1"; _t="$2"; _re="$3"; shift 3; _i=0; while [ "$_i" -lt "$_t" ]; do _c="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$@" "$_u" 2>/dev/null)"; printf '%s' "$_c" | grep -qE "$_re" && return 0; _i=$((_i+3)); sleep 3; done; say "!! $_u not answering ($_re) after $_t s (last ${_c:-none})"; return 1; }
wait_healthy() { _c="$1"; _t="${2:-180}"; _i=0; while [ "$_i" -lt "$_t" ]; do _s="$($RUNTIME inspect -f '{{.State.Health.Status}}' "$_c" 2>/dev/null || echo missing)"; [ "$_s" = healthy ] && return 0; _i=$((_i+3)); sleep 3; done; say "!! $_c not healthy after $_t s (last ${_s:-none})"; return 1; }

if [ "${1:-}" = "--down" ]; then
    [ -f "$STACK_DIR/.env" ] || : > "$STACK_DIR/.env"
    $COMPOSE down -v
    rm -f "$STACK_DIR/.env" "$STACK_DIR/tinyauth.env" "$STACK_DIR/keycloak/realm-sonar.json" \
          "$STACK_DIR/.demo-password"
    rm -rf "$STACK_DIR/tls"
    exit 0
fi

say "== SonarQube + Keycloak full-stack UAT (TLS, real OIDC login)"

# --- TLS -----------------------------------------------------------------
if [ ! -f "$CA" ]; then
    say "-- generating TLS CA + cert"
    mkdir -p "$STACK_DIR/tls"
    openssl genrsa -out "$STACK_DIR/tls/ca.key" 4096 2>/dev/null
    openssl req -x509 -new -nodes -key "$STACK_DIR/tls/ca.key" -sha256 -days 3650 \
        -out "$CA" -subj "/CN=SonarQube Stack UAT CA" 2>/dev/null
    SAN="subjectAltName=DNS:$APP_HOST,DNS:$AUTH_HOST,DNS:$KEYCLOAK_HOST,DNS:localhost,IP:127.0.0.1"
    openssl genrsa -out "$STACK_DIR/tls/tls.key" 2048 2>/dev/null
    openssl req -new -key "$STACK_DIR/tls/tls.key" -out "$STACK_DIR/tls/tls.csr" \
        -subj "/CN=$APP_HOST" -addext "$SAN" 2>/dev/null
    openssl x509 -req -in "$STACK_DIR/tls/tls.csr" -CA "$CA" -CAkey "$STACK_DIR/tls/ca.key" \
        -CAcreateserial -out "$STACK_DIR/tls/tls.crt" -days 365 -sha256 \
        -extfile /dev/stdin 2>/dev/null <<EOF
$SAN
EOF
    chmod 644 "$STACK_DIR/tls/tls.key" "$STACK_DIR/tls/tls.crt" "$CA"
fi

# --- podman socket for traefik ------------------------------------------
DOCKER_SOCKET=/var/run/docker.sock
if [ ! -S /var/run/docker.sock ]; then
    _sock="/run/user/$(id -u)/podman/podman.sock"
    [ -S "$_sock" ] || systemctl --user start podman.socket >/dev/null 2>&1 || true
    [ -S "$_sock" ] && DOCKER_SOCKET="$_sock"
fi

# --- secrets, .env, tinyauth.env, realm ---------------------------------
if [ ! -f "$STACK_DIR/.env" ]; then
    say "-- generating .env, tinyauth.env and Keycloak realm"
    DEMO_USER=demo
    DEMO_EMAIL=demo@example.com
    DEMO_PW="$(openssl rand -base64 12 | tr -d '/+=')"
    CLIENT_SECRET="$(openssl rand -hex 24)"
    printf '%s' "$DEMO_PW" > "$STACK_DIR/.demo-password"; chmod 600 "$STACK_DIR/.demo-password"
    {
        echo "COMPOSE_NET_NAME=sonar-stack"
        echo "NET_SUBNET=$NET_SUBNET"
        echo "TRAEFIK_IP=$TRAEFIK_IP"
        echo "BIND_ADDR=127.0.0.1"
        echo "TLS_PORT=$TLS_PORT"
        echo "APP_HOST=$APP_HOST"
        echo "AUTH_HOST=$AUTH_HOST"
        echo "KEYCLOAK_HOST=$KEYCLOAK_HOST"
        echo "KEYCLOAK_REALM=$REALM"
        echo "TLS_DIR=$STACK_DIR/tls"
        echo "DOCKER_SOCKET=$DOCKER_SOCKET"
        echo "KEYCLOAK_ADMIN_USER=admin"
        echo "KEYCLOAK_ADMIN_PASSWORD=$(openssl rand -base64 15 | tr -d '/+=')"
        echo "KEYCLOAK_DB_PASSWORD=$(openssl rand -hex 20)"
        echo "TINYAUTH_SECRET=$(openssl rand -hex 16)"
        echo "SONAR_DB_PASSWORD=$(openssl rand -hex 20)"
    } > "$STACK_DIR/.env"
    chmod 600 "$STACK_DIR/.env"
    {
        echo "GENERIC_CLIENT_ID=tinyauth"
        echo "GENERIC_CLIENT_SECRET=$CLIENT_SECRET"
    } > "$STACK_DIR/tinyauth.env"
    chmod 600 "$STACK_DIR/tinyauth.env"
    sed -e "s#@DEMO_USER@#$DEMO_USER#g" \
        -e "s#@DEMO_EMAIL@#$DEMO_EMAIL#g" \
        -e "s#@DEMO_PASSWORD@#$DEMO_PW#g" \
        -e "s#@CLIENT_ID@#tinyauth#g" \
        -e "s#@CLIENT_SECRET@#$CLIENT_SECRET#g" \
        -e "s#@REDIRECT_URI@#$LOGIN/api/oauth/callback/generic#g" \
        "$STACK_DIR/keycloak/realm-sonar.json.tmpl" > "$STACK_DIR/keycloak/realm-sonar.json"
fi
DEMO_USER=demo
DEMO_PW="$(cat "$STACK_DIR/.demo-password" 2>/dev/null)"

# --- staged bring-up -----------------------------------------------------
say "-- stage 1: databases"
$COMPOSE up -d --no-recreate keycloak-db sonar-db || exit 1
wait_healthy keycloak-db-sonar-stack 120 || exit 1
wait_healthy sonar-db-sonar-stack 120 || exit 1

say "-- stage 2: keycloak + proxy"
$COMPOSE up -d --no-recreate keycloak traefik || exit 1
wait_http "$ISSUER/.well-known/openid-configuration" 240 '^200$' --cacert "$CA" || {
    $RUNTIME logs --tail 30 keycloak-sonar-stack 2>&1 | sed 's/^/     /'; exit 1; }
pass "Keycloak realm '$REALM' imported and discoverable"

say "-- stage 3: sso gateway"
$COMPOSE up -d --no-recreate tinyauth || exit 1
wait_http "$LOGIN/" 90 '^(200|302|307)$' --cacert "$CA" || {
    $RUNTIME logs --tail 20 tinyauth-sonar-stack 2>&1 | sed 's/^/     /'; exit 1; }

say "-- stage 4: sonarqube (Elasticsearch + web, slow)"
$COMPOSE up -d --no-recreate sonarqube backups || exit 1
wait_healthy sonarqube-sonar-stack 420 || {
    $RUNTIME logs --tail 40 sonarqube-sonar-stack 2>&1 | sed 's/^/     /'; exit 1; }

say "== checks"
check 200 "Keycloak OIDC discovery (TLS)" --cacert "$CA" "$ISSUER/.well-known/openid-configuration"
check 401 "SonarQube rejects unauthenticated API" --cacert "$CA" "$APP/"
check 307 "SonarQube redirects browser to SSO" --cacert "$CA" -A "$UA" -H 'Accept: text/html' "$APP/"
check 401 "spoofed Remote-User without a session is rejected" --cacert "$CA" -H 'Remote-User: attacker' "$APP/"

# --- End-to-end: real Keycloak login through to a SonarQube session ------
# Drives the OIDC authorization-code flow the browser would: tinyauth hands
# out the Keycloak auth URL (with PKCE + a state cookie), the user submits
# credentials to Keycloak's login form, Keycloak redirects back to tinyauth
# with a code, tinyauth exchanges it and issues a session. That session is
# scoped Domain=localhost (valid for every *.localhost host); curl's
# public-suffix logic drops it from the jar, so it is captured from the
# callback and replayed explicitly — browsers keep it.
say "-- end-to-end Keycloak login (browser UA)"
JAR="$(mktemp)"
_authurl="$(curl -s -c "$JAR" --cacert "$CA" -A "$UA" "$LOGIN/api/oauth/url/generic" | jq -r '.url // empty')"
_form="$(curl -s -c "$JAR" -b "$JAR" --cacert "$CA" -A "$UA" "$_authurl")"
_action="$(printf '%s' "$_form" | grep -oE 'action="[^"]+"' | head -1 | sed 's/action="//;s/"$//' | sed 's/&amp;/\&/g')"
_loc="$(curl -s -c "$JAR" -b "$JAR" --cacert "$CA" -A "$UA" -i -X POST "$_action" \
    --data-urlencode "username=$DEMO_USER" --data-urlencode "password=$DEMO_PW" \
    --data-urlencode "credentialId=" | grep -i '^location:' | tail -1 | sed 's/[Ll]ocation: //I' | tr -d '\r')"
case "$_loc" in
    "$LOGIN/api/oauth/callback/generic"*)
        pass "Keycloak authenticates demo user and returns a code" ;;
    *)  fail "Keycloak authenticates demo user and returns a code" "redirect=$_loc" ;;
esac
SESSION="$(curl -s -c "$JAR" -b "$JAR" --cacert "$CA" -A "$UA" -D - "$_loc" -o /dev/null \
    | grep -i '^set-cookie: tinyauth-session' | sed -E 's/^set-cookie: ([^;]+);.*/\1/I' | tr -d '\r')"
rm -f "$JAR"
if [ -n "$SESSION" ]; then
    pass "tinyauth issues a session from the Keycloak identity"
else
    fail "tinyauth issues a session from the Keycloak identity" "no session cookie"
    say "== result: $PASS passed, $FAIL failed"; exit 1
fi

# The gateway's forwardAuth decision carries the Keycloak identity.
_ru="$(curl -s --cacert "$CA" -A "$UA" -H "Cookie: $SESSION" -D - "$LOGIN/api/auth/traefik" -o /dev/null \
    | grep -i '^remote-user:' | sed 's/remote-user: //I' | tr -d '\r')"
[ "$_ru" = "$DEMO_USER" ] \
    && pass "forwardAuth passes the Keycloak user to the app" "$_ru" \
    || fail "forwardAuth passes the Keycloak user to the app" "got '${_ru:-none}'"

# SonarQube signs the user in from that header — build → login, end to end.
_who="$(curl -s --cacert "$CA" -A "$UA" -H "Cookie: $SESSION" "$APP/api/users/current")"
if [ "$(printf '%s' "$_who" | jq -r '.login // empty')" = "$DEMO_USER" ] \
   && [ "$(printf '%s' "$_who" | jq -r '.local')" = "false" ]; then
    pass "SonarQube session created from Keycloak login" "$(printf '%s' "$_who" | jq -r '.login') (external)"
else
    fail "SonarQube session created from Keycloak login" "$(printf '%s' "$_who" | head -c 120)"
fi

check 200 "authenticated user loads SonarQube UI" --cacert "$CA" -A "$UA" -H "Cookie: $SESSION" "$APP/"

say ""
say "== stack"
say "SonarQube:  $APP"
say "Keycloak:   https://$KEYCLOAK_HOST:$TLS_PORT/admin/  (realm $REALM)"
say "Demo user:  $DEMO_USER / $DEMO_PW"
say "  Trust $STACK_DIR/tls/ca.crt in your browser, or accept the warning."
say "Tear down:  ./run-uat.sh --down"
say ""
say "== result: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
