#!/bin/sh
# UAT / smoke test for the tinyauth stack — TLS end to end, demonstrating
# the native integration pattern: traefik protects an app (whoami) with
# tinyauth's forwardAuth middleware. Unauthenticated requests bounce to
# the tinyauth login UI; that redirect is the integration proof.
#
#   ./run-uat.sh [--down]
#
# Browser access needs hosts entries:
#   127.0.0.1  app.localhost tinyauth.localhost
# (most systems already resolve *.localhost to 127.0.0.1).
set -u

cd "$(dirname "$0")"

COMPOSE_BIN="${COMPOSE:-podman-compose}"
COMPOSE="$COMPOSE_BIN -p tinyauth-uat -f docker-compose.uat.yml"
CA=tls/ca.crt
APP="https://app.localhost:8444"
LOGIN="https://tinyauth.localhost:8444"

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

wait_http() { # wait_http <url> <seconds> <accept-codes-regex> [curl args...]
    _u="$1"; _t="$2"; _re="$3"; shift 3
    _i=0
    while [ "$_i" -lt "$_t" ]; do
        _code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$@" "$_u" 2>/dev/null)"
        printf '%s' "$_code" | grep -qE "$_re" && return 0
        _i=$((_i + 2)); sleep 2
    done
    say "!! $_u not answering ($_re) after $_t s (last: ${_code:-none})"
    return 1
}

if [ "${1:-}" = "--down" ]; then
    $COMPOSE down -v
    rm -f .uat-password
    exit 0
fi

say "== tinyauth UAT (TLS + forwardAuth integration)"

if [ ! -f "$CA" ]; then
    say "-- generating TLS CA + certs into uat/tls"
    mkdir -p tls
    openssl genrsa -out tls/ca.key 4096 2>/dev/null
    openssl req -x509 -new -nodes -key tls/ca.key -sha256 -days 3650 \
        -out tls/ca.crt -subj "/CN=tinyauth UAT CA" 2>/dev/null
    SAN="subjectAltName=DNS:app.localhost,DNS:tinyauth.localhost,DNS:localhost,IP:127.0.0.1"
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
    say "-- generating uat/.env credentials + local user"
    UAT_PW="$(openssl rand -base64 15 | tr -d '/+=')"
    USERS_LINE="$(htpasswd -nbB uat-admin "$UAT_PW")"
    {
        echo "PORT=3000"
        echo "ADDRESS=0.0.0.0"
        echo "SECRET=$(openssl rand -hex 16)"
        echo "APP_URL=$LOGIN"
        echo "USERS=$USERS_LINE"
        echo "COOKIE_SECURE=true"
        echo "APP_TITLE=Tinyauth UAT"
    } > .env
    printf '%s' "$UAT_PW" > .uat-password
    chmod 600 .uat-password
fi

# Point traefik's docker provider at the rootless podman socket when the
# default docker socket isn't available.
if [ ! -S /var/run/docker.sock ]; then
    USER_SOCK="/run/user/$(id -u)/podman/podman.sock"
    if [ ! -S "$USER_SOCK" ]; then
        systemctl --user start podman.socket >/dev/null 2>&1 || true
    fi
    [ -S "$USER_SOCK" ] && export DOCKER_SOCKET="$USER_SOCK"
fi

say "-- starting traefik, tinyauth, protected whoami"
$COMPOSE up -d --no-recreate || exit 1
# tinyauth answers its own health directly; the protected app answers via
# traefik once routers are live.
wait_http "$LOGIN/" 60 '^(200|302|307)$' --cacert "$CA" || {
    podman logs --tail 20 tinyauth-uat 2>&1 | sed 's/^/     /'; exit 1;
}

say "== checks"
# An unauthenticated API request to the protected app is rejected by the
# tinyauth forwardAuth middleware (401 — whoami is never reached).
check 401 "protected app rejects unauthenticated API" --cacert "$CA" "$APP/"
# A browser request (Accept: text/html) is redirected to the login UI.
check 307 "protected app redirects browser to login"  --cacert "$CA" -H 'Accept: text/html' "$APP/"
check 200 "tinyauth login UI (TLS)"                    -L --cacert "$CA" "$LOGIN/"

_loc="$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 15 --cacert "$CA" -H 'Accept: text/html' "$APP/")"
case "$_loc" in
    *tinyauth.localhost:8444/login*redirect_uri*)
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "redirect targets tinyauth login w/ return URL" "OK" ;;
    *)
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s %s\n' "redirect targets tinyauth login w/ return URL" "$_loc" ;;
esac

UAT_PW="$(cat .uat-password 2>/dev/null)"

# --- Full end-to-end login (browser User-Agent) ---------------------------
# Log in with the generated user, then use the resulting session cookie to
# reach the protected whoami app. tinyauth scopes the cookie to Domain=
# localhost (valid for both app.localhost and tinyauth.localhost); we send
# it explicitly because curl's public-suffix logic drops single-label
# domains from its jar (browsers keep it).
say "-- end-to-end login (browser UA)"
UA="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
SC="$(curl -s --cacert "$CA" -A "$UA" -D - -H 'Content-Type: application/json' \
    -X POST "$LOGIN/api/login" -d "{\"username\":\"uat-admin\",\"password\":\"$UAT_PW\"}" -o /dev/null \
    | grep -i '^set-cookie:' | sed -E 's/^set-cookie: ([^;]+);.*/\1/I')"
if [ -n "$SC" ]; then
    _dec="$(curl -s --cacert "$CA" -A "$UA" -H "Cookie: $SC" -o /dev/null -w '%{http_code}' "$LOGIN/api/auth/traefik")"
    _app="$(curl -s --cacert "$CA" -A "$UA" -H "Cookie: $SC" -o /tmp/ta_e2e.$$ -w '%{http_code}' "$APP/")"
    if [ "$_dec" = "200" ] && [ "$_app" = "200" ] && grep -qi 'Hostname:' /tmp/ta_e2e.$$; then
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "E2E: login -> session -> protected app reached" "whoami OK"
    else
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s decision=%s app=%s\n' "E2E: login -> session -> protected app reached" "$_dec" "$_app"
    fi
    rm -f /tmp/ta_e2e.$$
else
    FAIL=$((FAIL + 1)); printf '  FAIL  %-58s %s\n' "E2E: login -> session -> protected app reached" "no session cookie"
fi

say ""
say "== result: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
    say ""
    say "Protected app:  $APP     (bounces to login until authenticated)"
    say "Login UI:       $LOGIN   (uat-admin / $UAT_PW)"
    say "  After logging in you are redirected back to the protected whoami app."
    say "  Trust $(pwd)/tls/ca.crt in your browser (or accept the warnings)."
    say "Tear down:      ./run-uat.sh --down"
fi
[ "$FAIL" -eq 0 ]
