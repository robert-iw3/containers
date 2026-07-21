#!/bin/sh
# UAT / smoke test for the Keycloak stack — TLS end to end, plus a mock
# relying application (oauth2-proxy + whoami) that authenticates against
# Keycloak over OIDC to demonstrate IdP integration.
#
#   ./run-uat.sh [--down]
#
# The stack stays up for manual login; --down tears it down.
set -u

cd "$(dirname "$0")"

COMPOSE_BIN="${COMPOSE:-podman-compose}"
COMPOSE="$COMPOSE_BIN -p keycloak-uat -f docker-compose.uat.yml"
BASE=https://localhost:8543
APP=https://localhost:4184
CA=tls/ca.crt
UA="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

PASS=0
FAIL=0

say() { printf '%s\n' "$*"; }

check() { # check <expected_code> <description> [curl args...]
    _want="$1"; _desc="$2"; shift 2
    _got="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@")"
    if [ "$_got" = "$_want" ]; then
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "$_desc" "$_got"
    else
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s got %s want %s\n' "$_desc" "$_got" "$_want"
    fi
}

wait_healthy() { # wait_healthy <container> <seconds>
    _i=0
    while [ "$_i" -lt "$2" ]; do
        if [ "$(podman inspect --format '{{.State.Health.Status}}' "$1" 2>/dev/null)" = "healthy" ]; then
            return 0
        fi
        _i=$((_i + 2)); sleep 2
    done
    say "!! $1 not healthy after $2 s"
    podman logs --tail 15 "$1" 2>&1 | sed 's/^/     /'
    return 1
}

wait_http() { # wait_http <url> <seconds> [curl args...]
    _u="$1"; _t="$2"; shift 2
    _i=0
    while [ "$_i" -lt "$_t" ]; do
        _code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$@" "$_u" 2>/dev/null)"
        [ "$_code" = "200" ] && return 0
        _i=$((_i + 2)); sleep 2
    done
    say "!! $_u not answering 200 after $_t s"
    return 1
}

kcadm() {
    podman exec keycloak-uat /opt/keycloak/bin/kcadm.sh "$@"
}

if [ "${1:-}" = "--down" ]; then
    $COMPOSE down -v
    rm -f .uat-demo-password
    exit 0
fi

say "== keycloak UAT (TLS + OIDC relying app)"

if [ ! -f .env ]; then
    say "-- generating uat/.env credentials"
    {
        echo "POSTGRESQL_USERNAME=keycloak"
        echo "POSTGRESQL_PASSWORD=$(openssl rand -hex 20)"
        echo "POSTGRESQL_DATABASE=keycloak"
        echo "KEYCLOAK_USER=admin"
        echo "KEYCLOAK_PASSWORD=$(openssl rand -base64 15 | tr -d '/+=')"
    } > .env
fi

if [ ! -f "$CA" ]; then
    say "-- generating TLS CA + certs into uat/tls"
    mkdir -p tls
    openssl genrsa -out tls/ca.key 4096 2>/dev/null
    openssl req -x509 -new -nodes -key tls/ca.key -sha256 -days 3650 \
        -out tls/ca.crt -subj "/CN=Keycloak UAT CA" 2>/dev/null
    SAN="subjectAltName=DNS:localhost,DNS:keycloak,IP:127.0.0.1"
    openssl genrsa -out tls/tls.key 2048 2>/dev/null
    openssl req -new -key tls/tls.key -out tls/tls.csr \
        -subj "/CN=localhost" -addext "$SAN" 2>/dev/null
    openssl x509 -req -in tls/tls.csr -CA tls/ca.crt -CAkey tls/ca.key \
        -CAcreateserial -out tls/tls.crt -days 365 -sha256 \
        -extfile /dev/stdin 2>/dev/null <<EOF
$SAN
EOF
    chmod 644 tls/tls.key tls/tls.crt tls/ca.crt
fi

# oauth2-proxy.env must exist before compose starts the service
if [ ! -f oauth2-proxy.env ]; then
    {
        echo "OAUTH2_PROXY_CLIENT_ID=uat-app"
        echo "OAUTH2_PROXY_CLIENT_SECRET=$(openssl rand -hex 20)"
        echo "OAUTH2_PROXY_COOKIE_SECRET=$(openssl rand -base64 32 | tr -- '+/' '-_')"
    } > oauth2-proxy.env
fi

say "-- starting postgres"
$COMPOSE up -d postgres || exit 1
wait_healthy postgres-keycloak-uat 120 || exit 1

say "-- starting keycloak"
$COMPOSE up -d --no-recreate keycloak || exit 1
# When a TLS cert is configured, the management port (9000) also serves
# HTTPS — using the same cert — even with KC_HTTP_ENABLED=true.
wait_http "https://127.0.0.1:9001/health/ready" 240 --cacert "$CA" || {
    podman logs --tail 20 keycloak-uat 2>&1 | sed 's/^/     /'; exit 1;
}

say "-- bootstrapping demo realm, user and OIDC client (kcadm)"
KC_PW="$(grep '^KEYCLOAK_PASSWORD=' .env | cut -d= -f2-)"
CLIENT_SECRET="$(grep '^OAUTH2_PROXY_CLIENT_SECRET=' oauth2-proxy.env | cut -d= -f2-)"
kcadm config credentials --server http://localhost:8080 \
    --realm master --user admin --password "$KC_PW" || exit 1
if ! kcadm get realms/uat >/dev/null 2>&1; then
    kcadm create realms -s realm=uat -s enabled=true || exit 1
    kcadm create users -r uat -s username=demo -s enabled=true \
        -s email=demo@uat.local -s emailVerified=true \
        -s firstName=Demo -s lastName=User || exit 1
    DEMO_PW="$(openssl rand -base64 12 | tr -d '/+=')"
    printf '%s' "$DEMO_PW" > .uat-demo-password
    chmod 600 .uat-demo-password
    kcadm set-password -r uat --username demo --new-password "$DEMO_PW" || exit 1
    kcadm create clients -r uat \
        -s clientId=uat-app \
        -s protocol=openid-connect \
        -s publicClient=false \
        -s "secret=$CLIENT_SECRET" \
        -s 'redirectUris=["https://localhost:4184/oauth2/callback"]' \
        -s standardFlowEnabled=true || exit 1
fi
DEMO_PW="$(cat .uat-demo-password 2>/dev/null)"

say "-- starting mock relying application (oauth2-proxy + whoami)"
# oauth2-proxy performs OIDC discovery against Keycloak over TLS at
# startup and exits if it fails, so reaching /ping already proves the
# integration handshake succeeded.
$COMPOSE up -d --no-recreate whoami oauth2-proxy || exit 1
wait_http "$APP/ping" 60 --cacert "$CA" || {
    podman logs --tail 20 oauth2-proxy-keycloak-uat 2>&1 | sed 's/^/     /'; exit 1;
}

say "== checks"
check 200 "uat realm OIDC discovery (TLS)" --cacert "$CA" "$BASE/realms/uat/.well-known/openid-configuration"
check 302 "admin console redirect"         --cacert "$CA" "$BASE/admin"
check 200 "admin console"                  -L --cacert "$CA" "$BASE/admin/master/console/"
check 200 "mock app health (/ping)"        --cacert "$CA" "$APP/ping"
check 302 "mock app starts OIDC flow"      --cacert "$CA" "$APP/"

# Prove the mock app's login redirect targets *our* Keycloak realm.
_loc="$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 15 --cacert "$CA" "$APP/oauth2/start")"
case "$_loc" in
    *localhost:8543/realms/uat/protocol/openid-connect/auth*)
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "mock app auth redirect -> keycloak uat realm" "OK" ;;
    *)
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s %s\n' "mock app auth redirect -> keycloak uat realm" "$_loc" ;;
esac

# --- Full end-to-end login (browser User-Agent) ---------------------------
# Drive the complete OIDC authorization-code flow the way a browser would:
# start at the mock app, submit the demo user's credentials to the Keycloak
# login form, follow the callback, and assert the protected whoami upstream
# is reached with the identity headers oauth2-proxy injects. This proves the
# whole chain (app -> Keycloak login -> token -> session -> upstream) works.
say "-- end-to-end login (demo user, browser UA)"
E2E_JAR="$(mktemp)"; E2E_OUT="$(mktemp)"
LOGIN_HTML="$(curl -s --cacert "$CA" -A "$UA" -H 'Accept: text/html' -c "$E2E_JAR" -b "$E2E_JAR" -L "$APP/oauth2/start?rd=%2F")"
ACTION="$(printf '%s' "$LOGIN_HTML" | grep -oE 'action="[^"]*login-actions/authenticate[^"]*"' | head -1 | sed 's/^action="//; s/"$//; s/&amp;/\&/g')"
if [ -n "$ACTION" ]; then
    E2E_CODE="$(curl -s --cacert "$CA" -A "$UA" -H 'Accept: text/html' -c "$E2E_JAR" -b "$E2E_JAR" -L -o "$E2E_OUT" -w '%{http_code}' \
        --data-urlencode "username=demo" --data-urlencode "password=$DEMO_PW" --data-urlencode "credentialId=" "$ACTION")"
    if [ "$E2E_CODE" = "200" ] && grep -q "X-Forwarded-Preferred-Username: demo" "$E2E_OUT"; then
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "E2E: demo logs in and reaches protected app" "whoami OK"
    else
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s http=%s\n' "E2E: demo logs in and reaches protected app" "$E2E_CODE"
    fi
else
    FAIL=$((FAIL + 1)); printf '  FAIL  %-58s %s\n' "E2E: demo logs in and reaches protected app" "no login form"
fi
rm -f "$E2E_JAR" "$E2E_OUT"

say ""
say "== result: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
    say ""
    say "Admin console:  $BASE/admin   (admin / $KC_PW)"
    say "Mock app:       $APP          (demo / $DEMO_PW)"
    say "  Opening the mock app runs the full OIDC auth-code flow against"
    say "  Keycloak and then proxies the whoami upstream with identity headers."
    say "  Trust $(pwd)/tls/ca.crt in your browser (or accept the warnings)."
    say "Tear down:      ./run-uat.sh --down"
fi
[ "$FAIL" -eq 0 ]
