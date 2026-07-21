#!/bin/sh
# UAT / smoke test for the ZITADEL stack — TLS end to end, plus a mock
# relying application (oauth2-proxy + whoami) that authenticates against
# ZITADEL over OIDC. The OIDC application is created via the management
# API using a bootstrapped machine-user PAT.
#
#   ./run-uat.sh [--down]
#
# The stack stays up for manual login; --down tears it down.
set -u

cd "$(dirname "$0")"

COMPOSE_BIN="${COMPOSE:-podman-compose}"
COMPOSE="$COMPOSE_BIN -p zitadel-uat -f docker-compose.uat.yml"
BASE=https://localhost:8443
APP=https://localhost:4186
CA=tls/ca.crt

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
        _i=$((_i + 3)); sleep 3
    done
    say "!! $1 not healthy after $2 s"
    podman logs --tail 20 "$1" 2>&1 | sed 's/^/     /'
    return 1
}

wait_http() { # wait_http <url> <seconds> [curl args...]
    _u="$1"; _t="$2"; shift 2
    _i=0
    while [ "$_i" -lt "$_t" ]; do
        _code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$@" "$_u" 2>/dev/null)"
        [ "$_code" = "200" ] && return 0
        _i=$((_i + 3)); sleep 3
    done
    say "!! $_u not answering 200 after $_t s"
    return 1
}

if [ "${1:-}" = "--down" ]; then
    $COMPOSE down -v
    rm -f oauth2-proxy.env
    exit 0
fi

say "== zitadel UAT (TLS + OIDC relying app)"

if [ ! -f "$CA" ]; then
    say "-- generating TLS CA + certs into uat/tls"
    mkdir -p tls
    openssl genrsa -out tls/ca.key 4096 2>/dev/null
    openssl req -x509 -new -nodes -key tls/ca.key -sha256 -days 3650 \
        -out tls/ca.crt -subj "/CN=ZITADEL UAT CA" 2>/dev/null
    SAN="subjectAltName=DNS:localhost,IP:127.0.0.1"
    openssl genrsa -out tls/tls.key 2048 2>/dev/null
    openssl req -new -key tls/tls.key -out tls/tls.csr \
        -subj "/CN=localhost" -addext "$SAN" 2>/dev/null
    openssl x509 -req -in tls/tls.csr -CA tls/ca.crt -CAkey tls/ca.key \
        -CAcreateserial -out tls/tls.crt -days 365 -sha256 \
        -extfile /dev/stdin 2>/dev/null <<EOF
$SAN
EOF
fi
chmod 644 tls/tls.key tls/tls.crt tls/ca.crt

if [ ! -f .env ]; then
    say "-- generating uat/.env credentials"
    {
        echo "POSTGRES_PASSWORD=$(openssl rand -hex 20)"
        echo "ZITADEL_MASTERKEY=$(openssl rand -hex 16)"
        echo "ZITADEL_ADMIN_PASSWORD=$(openssl rand -base64 12 | tr -d '/+=')Aa1!"
    } > .env
fi
# podman-compose reads .env from the compose dir automatically.

say "-- starting postgres"
$COMPOSE up -d --no-recreate postgres || exit 1
wait_healthy postgres-zitadel-uat 120 || exit 1

say "-- starting zitadel-api (first init runs migrations; can take a while)"
$COMPOSE up -d --no-recreate zitadel-api || exit 1
# Gate on `zitadel ready` rather than container health (which flaps
# during the long first-run init).
_i=0
while [ "$_i" -lt 420 ]; do
    podman exec zitadel-api-uat /app/zitadel ready >/dev/null 2>&1 && break
    _i=$((_i + 5)); sleep 5
done
if [ "$_i" -ge 420 ]; then
    say "!! zitadel-api not ready after 420 s"
    podman logs --tail 20 zitadel-api-uat 2>&1 | sed 's/^/     /'; exit 1
fi

# Login must be resolvable before nginx starts (nginx resolves upstream
# names at startup), so bring it up before the proxy.
say "-- starting login v2"
$COMPOSE up -d --no-recreate zitadel-login || exit 1
sleep 4

say "-- starting tls proxy"
$COMPOSE up -d --no-recreate proxy || exit 1
wait_http "$BASE/.well-known/openid-configuration" 60 --cacert "$CA" || {
    podman logs --tail 15 zitadel-proxy-uat 2>&1 | sed 's/^/     /'; exit 1;
}

say "-- creating OIDC application via management API (machine PAT)"
# The zitadel image is distroless (no cat); read the PAT from the shared
# bootstrap volume with a busybox helper instead.
BOOT_VOL="$(podman volume ls --format '{{.Name}}' | grep 'zitadel-uat.*bootstrap' | head -1)"
# Idempotent: only create the project + OIDC app on the first run (when
# oauth2-proxy.env doesn't yet exist). Re-runs reuse the existing app.
if [ ! -f oauth2-proxy.env ]; then
    PAT="$(podman run --rm -v "$BOOT_VOL":/b:ro docker.io/library/busybox cat /b/admin.pat 2>/dev/null)"
    if [ -z "$PAT" ]; then
        say "!! could not read bootstrap PAT (volume: $BOOT_VOL)"; exit 1
    fi
    PROJECT_ID="$(curl -s --cacert "$CA" -X POST "$BASE/management/v1/projects" \
        -H "Authorization: Bearer $PAT" -H "Content-Type: application/json" \
        -d '{"name":"UAT"}' | jq -r '.id // empty')"
    if [ -z "$PROJECT_ID" ]; then
        say "!! project creation failed"; exit 1
    fi
    APP_JSON="$(curl -s --cacert "$CA" -X POST "$BASE/management/v1/projects/$PROJECT_ID/apps/oidc" \
        -H "Authorization: Bearer $PAT" -H "Content-Type: application/json" \
        -d '{
            "name":"uat-app",
            "redirectUris":["https://localhost:4186/oauth2/callback"],
            "responseTypes":["OIDC_RESPONSE_TYPE_CODE"],
            "grantTypes":["OIDC_GRANT_TYPE_AUTHORIZATION_CODE"],
            "appType":"OIDC_APP_TYPE_WEB",
            "authMethodType":"OIDC_AUTH_METHOD_TYPE_BASIC",
            "devMode":true
        }')"
    CLIENT_ID="$(printf '%s' "$APP_JSON" | jq -r '.clientId // empty')"
    CLIENT_SECRET="$(printf '%s' "$APP_JSON" | jq -r '.clientSecret // empty')"
    if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
        say "!! OIDC app creation failed: $APP_JSON"; exit 1
    fi
    {
        echo "OAUTH2_PROXY_CLIENT_ID=$CLIENT_ID"
        echo "OAUTH2_PROXY_CLIENT_SECRET=$CLIENT_SECRET"
        echo "OAUTH2_PROXY_COOKIE_SECRET=$(openssl rand -base64 32 | tr -- '+/' '-_')"
    } > oauth2-proxy.env
else
    say "   (reusing existing OIDC app from oauth2-proxy.env)"
fi

say "-- starting mock relying application (oauth2-proxy + whoami)"
$COMPOSE up -d --no-recreate whoami oauth2-proxy || exit 1
wait_http "$APP/ping" 60 --cacert "$CA" || {
    podman logs --tail 20 oauth2-proxy-zitadel-uat 2>&1 | sed 's/^/     /'; exit 1;
}

say "== checks"
check 200 "OIDC discovery (TLS)"      --cacert "$CA" "$BASE/.well-known/openid-configuration"
check 200 "login v2 healthy"          --cacert "$CA" "$BASE/ui/v2/login/healthy"
check 200 "mock app health (/ping)"   --cacert "$CA" "$APP/ping"
check 302 "mock app starts OIDC flow" --cacert "$CA" "$APP/"

_loc="$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 15 --cacert "$CA" "$APP/oauth2/start")"
case "$_loc" in
    *localhost:8443/oauth/v2/authorize*)
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "mock app auth redirect -> zitadel" "OK" ;;
    *)
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s %s\n' "mock app auth redirect -> zitadel" "$_loc" ;;
esac

ADMIN_PW="$(grep '^ZITADEL_ADMIN_PASSWORD=' .env | cut -d= -f2-)"

# --- Full end-to-end login (browser User-Agent) ---------------------------
# Complete the OIDC auth-code flow using ZITADEL's session API — exactly
# what the v2 login UI calls internally: start at the mock app to mint an
# auth request, create a session with a user+password check, finalize the
# auth request against that session to obtain the callback, then follow it
# through oauth2-proxy and assert the protected whoami upstream is reached.
say "-- end-to-end login (admin, browser UA, session API)"
UA="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
LOGIN_PAT="$(podman run --rm -v "$BOOT_VOL":/b:ro docker.io/library/busybox cat /b/login-client.pat 2>/dev/null)"
E2E_JAR="$(mktemp)"; E2E_OUT="$(mktemp)"
_eff="$(curl -s --cacert "$CA" -A "$UA" -c "$E2E_JAR" -b "$E2E_JAR" -L -o /dev/null -w '%{url_effective}' "$APP/oauth2/start")"
_reqid="$(printf '%s' "$_eff" | sed -nE 's/.*requestId=([^&]+).*/\1/p')"; _reqid="${_reqid#oidc_}"
_sess="$(curl -s --cacert "$CA" -H "Authorization: Bearer $LOGIN_PAT" -H 'Content-Type: application/json' -X POST "$BASE/v2/sessions" \
    -d "{\"checks\":{\"user\":{\"loginName\":\"zitadel-admin@zitadel.localhost\"},\"password\":{\"password\":\"$ADMIN_PW\"}}}")"
_sid="$(printf '%s' "$_sess" | jq -r '.sessionId // empty')"; _stok="$(printf '%s' "$_sess" | jq -r '.sessionToken // empty')"
if [ -n "$_reqid" ] && [ -n "$_sid" ]; then
    _cb="$(curl -s --cacert "$CA" -H "Authorization: Bearer $LOGIN_PAT" -H 'Content-Type: application/json' -X POST "$BASE/v2/oidc/auth_requests/$_reqid" \
        -d "{\"session\":{\"sessionId\":\"$_sid\",\"sessionToken\":\"$_stok\"}}" | jq -r '.callbackUrl // empty')"
    if [ -n "$_cb" ]; then
        _code="$(curl -s --cacert "$CA" -A "$UA" -c "$E2E_JAR" -b "$E2E_JAR" -L -o "$E2E_OUT" -w '%{http_code}' "$_cb")"
        if [ "$_code" = "200" ] && grep -q "X-Forwarded-Preferred-Username: zitadel-admin" "$E2E_OUT"; then
            PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "E2E: admin logs in and reaches protected app" "whoami OK"
        else
            FAIL=$((FAIL + 1)); printf '  FAIL  %-58s http=%s\n' "E2E: admin logs in and reaches protected app" "$_code"
        fi
    else
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s %s\n' "E2E: admin logs in and reaches protected app" "no callbackUrl"
    fi
else
    FAIL=$((FAIL + 1)); printf '  FAIL  %-58s reqid=%s sid=%s\n' "E2E: admin logs in and reaches protected app" "$_reqid" "$_sid"
fi
rm -f "$E2E_JAR" "$E2E_OUT"
say ""
say "== result: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
    say ""
    say "Console/login:  $BASE/ui/console"
    say "  human admin:  zitadel-admin@zitadel.localhost / $ADMIN_PW"
    say "  (uat-admin-sa is a machine/service account for the API only —"
    say "   it has no password and cannot log in interactively)"
    say "Mock app:       $APP"
    say "  Opening the mock app runs the full OIDC auth-code flow against"
    say "  ZITADEL and then proxies the whoami upstream with identity headers."
    say "  Trust $(pwd)/tls/ca.crt in your browser (or accept the warnings)."
    say "Tear down:      ./run-uat.sh --down"
fi
[ "$FAIL" -eq 0 ]
