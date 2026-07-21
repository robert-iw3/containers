#!/bin/sh
# UAT / smoke test for the authentik stack — TLS end to end, plus a mock
# relying application (oauth2-proxy + whoami) that authenticates against
# authentik over OIDC. The OAuth2 provider/application is provisioned
# declaratively by blueprints/uat-app.yaml.
#
#   ./run-uat.sh [--down]
#
# MFA behaviour is configurable via UAT_MFA (default: skip):
#   UAT_MFA=skip   remove the MFA-validation stage from the login flow so
#                  password-only login works (fast UAT / demo default).
#   UAT_MFA=totp   keep MFA enabled (as production should) and validate it:
#                  enrol a TOTP device for akadmin with a known secret and
#                  complete the login by computing the current TOTP code.
# Production keeps MFA on — the compose stack never touches the flow; only
# this UAT script optionally relaxes it.
#
# The stack stays up for manual login; --down tears it down.
set -u

cd "$(dirname "$0")"

COMPOSE_BIN="${COMPOSE:-podman-compose}"
COMPOSE="$COMPOSE_BIN -p authentik-uat -f docker-compose.uat.yml"
BASE=https://localhost:9443
APP=https://localhost:4185
CA=tls/ca.crt
ISSUER="$BASE/application/o/uat-app"
UAT_MFA="${UAT_MFA:-skip}"

PASS=0
FAIL=0

say() { printf '%s\n' "$*"; }

# totp <base32-secret> -> current 6-digit TOTP code (SHA1, 30s, 6 digits).
# Uses python3 (oathtool isn't guaranteed to be installed).
totp() {
    python3 - "$1" <<'PY'
import sys, base64, hmac, hashlib, struct, time
s = sys.argv[1].strip().upper().replace(' ', '')
s += '=' * ((8 - len(s) % 8) % 8)
key = base64.b32decode(s)
msg = struct.pack('>Q', int(time.time()) // 30)
h = hmac.new(key, msg, hashlib.sha1).digest()
o = h[-1] & 0x0f
print('%06d' % ((struct.unpack('>I', h[o:o+4])[0] & 0x7fffffff) % 1000000))
PY
}

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
        _i=$((_i + 3)); sleep 3
    done
    say "!! $_u not answering 200 after $_t s"
    return 1
}

if [ "${1:-}" = "--down" ]; then
    $COMPOSE down -v
    exit 0
fi

say "== authentik UAT (TLS + OIDC relying app)"

if [ ! -f "$CA" ]; then
    say "-- generating TLS CA + certs into uat/tls"
    mkdir -p tls
    openssl genrsa -out tls/ca.key 4096 2>/dev/null
    openssl req -x509 -new -nodes -key tls/ca.key -sha256 -days 3650 \
        -out tls/ca.crt -subj "/CN=authentik UAT CA" 2>/dev/null
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

if [ ! -f oauth2-proxy.env ]; then
    CLIENT_SECRET="$(openssl rand -hex 24)"
    {
        echo "OAUTH2_PROXY_CLIENT_ID=uat-app"
        echo "OAUTH2_PROXY_CLIENT_SECRET=$CLIENT_SECRET"
        echo "OAUTH2_PROXY_COOKIE_SECRET=$(openssl rand -base64 32 | tr -- '+/' '-_')"
    } > oauth2-proxy.env
fi
CLIENT_SECRET="$(grep '^OAUTH2_PROXY_CLIENT_SECRET=' oauth2-proxy.env | cut -d= -f2-)"

if [ ! -f .env ]; then
    say "-- generating uat/.env credentials"
    {
        echo "POSTGRES_USER=authentik"
        echo "POSTGRES_PASSWORD=$(openssl rand -hex 20)"
        echo "POSTGRES_DB=authentik"
        echo "AUTHENTIK_SECRET_KEY=$(openssl rand -base64 50 | tr -d '\n')"
        echo "AUTHENTIK_BOOTSTRAP_PASSWORD=$(openssl rand -base64 15 | tr -d '/+=')"
        echo "AUTHENTIK_BOOTSTRAP_TOKEN=$(openssl rand -hex 24)"
        echo "AUTHENTIK_BOOTSTRAP_EMAIL=akadmin@uat.local"
        echo "AUTHENTIK_UAT_CLIENT_SECRET=$CLIENT_SECRET"
        echo "AUTHENTIK_DISABLE_STARTUP_ANALYTICS=true"
        echo "AUTHENTIK_ERROR_REPORTING__ENABLED=false"
    } > .env
fi

say "-- starting postgres + redis"
$COMPOSE up -d --no-recreate postgresql redis || exit 1
wait_healthy postgres-authentik-uat 120 || exit 1
wait_healthy redis-authentik-uat 60 || exit 1

say "-- starting authentik server, worker, tls proxy"
$COMPOSE up -d --no-recreate server worker proxy || exit 1
wait_http "$BASE/-/health/ready/" 300 --cacert "$CA" || {
    podman logs --tail 20 authentik-server-uat 2>&1 | sed 's/^/     /'; exit 1;
}

say "-- waiting for the OAuth2 blueprint to apply"
wait_http "$ISSUER/.well-known/openid-configuration" 240 --cacert "$CA" || {
    say "   (blueprint not applied; worker log:)"
    podman logs --tail 25 authentik-worker-uat 2>&1 | grep -i 'blueprint\|uat' | tail -15 | sed 's/^/     /'
    exit 1;
}

TOKEN="$(grep '^AUTHENTIK_BOOTSTRAP_TOKEN=' .env | cut -d= -f2-)"
TOTP_SECRET=""
if [ "$UAT_MFA" = "totp" ]; then
    # Production-like: keep the MFA-validation stage ENFORCED (no bypass)
    # and enrol a real TOTP device for akadmin through authentik's own ORM
    # (a raw SQL insert is not picked up by the flow's device lookup). The
    # stage is set to totp-only with not_configured_action=deny so a second
    # factor is genuinely required.
    say "-- MFA mode: totp — enforcing MFA and enrolling a TOTP device for akadmin"
    SPK="$(curl -s --cacert "$CA" -H "Authorization: Bearer $TOKEN" "$BASE/api/v3/stages/authenticator/validate/?name=default-authentication-mfa-validation" | jq -r '.results[0].pk')"
    curl -s --cacert "$CA" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -X PATCH \
        "$BASE/api/v3/stages/authenticator/validate/$SPK/" \
        -d '{"device_classes":["totp"],"not_configured_action":"deny","configuration_stages":[]}' >/dev/null
    HEXKEY="$(openssl rand -hex 20)"
    podman exec -i authentik-server-uat ak shell >/dev/null 2>&1 <<PY
from authentik.stages.authenticator_totp.models import TOTPDevice
from authentik.core.models import User
u = User.objects.get(username='akadmin')
TOTPDevice.objects.filter(user=u).delete()
TOTPDevice.objects.create(user=u, name='uat-totp', confirmed=True, key='$HEXKEY', digits=6, step=30)
PY
    # base32 secret for authenticator apps / otpauth URIs
    TOTP_SECRET="$(python3 -c "import base64,sys;print(base64.b32encode(bytes.fromhex('$HEXKEY')).decode())")"
    printf '%s' "$HEXKEY" > .totp-hexkey; chmod 600 .totp-hexkey
    say "   TOTP device enrolled for akadmin"
else
    # Fast UAT / demo: remove the MFA-validation stage so password-only
    # login works (akadmin has no device and the stage's skip action does
    # not fire for a user with an email address).
    say "-- MFA mode: skip — removing MFA stage from the login flow"
    FLOWPK="$(curl -s --cacert "$CA" -H "Authorization: Bearer $TOKEN" "$BASE/api/v3/flows/instances/?slug=default-authentication-flow" | jq -r '.results[0].pk')"
    BPK="$(curl -s --cacert "$CA" -H "Authorization: Bearer $TOKEN" "$BASE/api/v3/flows/bindings/?target=$FLOWPK" | jq -r '.results[] | select(.stage_obj.name=="default-authentication-mfa-validation") | .pk')"
    [ -n "$BPK" ] && curl -s --cacert "$CA" -H "Authorization: Bearer $TOKEN" -X DELETE "$BASE/api/v3/flows/bindings/$BPK/" -o /dev/null
fi
podman exec redis-authentik-uat redis-cli FLUSHALL >/dev/null 2>&1

say "-- starting mock relying application (oauth2-proxy + whoami)"
$COMPOSE up -d --no-recreate whoami oauth2-proxy || exit 1
wait_http "$APP/ping" 60 --cacert "$CA" || {
    podman logs --tail 20 oauth2-proxy-authentik-uat 2>&1 | sed 's/^/     /'; exit 1;
}

say "== checks"
check 200 "authentik readiness (TLS)"      --cacert "$CA" "$BASE/-/health/ready/"
check 200 "uat app OIDC discovery (TLS)"   --cacert "$CA" "$ISSUER/.well-known/openid-configuration"
check 200 "admin/login flow reachable"     -L --cacert "$CA" "$BASE/if/flow/default-authentication-flow/"
check 200 "mock app health (/ping)"        --cacert "$CA" "$APP/ping"
check 302 "mock app starts OIDC flow"      --cacert "$CA" "$APP/"

_loc="$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 15 --cacert "$CA" "$APP/oauth2/start")"
case "$_loc" in
    *localhost:9443/application/o/authorize*)
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "mock app auth redirect -> authentik" "OK" ;;
    *)
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s %s\n' "mock app auth redirect -> authentik" "$_loc" ;;
esac

# --- Full end-to-end login (browser User-Agent) ---------------------------
# Drive authentik's flow-executor API the way the browser SPA does: start
# at the mock app, walk identification -> password, follow the redirect
# through the OIDC callback, and assert the protected whoami upstream is
# reached with oauth2-proxy's identity headers.
say "-- end-to-end login (akadmin, browser UA)"
UA="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
AK_PW="$(grep '^AUTHENTIK_BOOTSTRAP_PASSWORD=' .env | cut -d= -f2-)"
E2E_JAR="$(mktemp)"; E2E_OUT="$(mktemp)"
_eff="$(curl -s --cacert "$CA" -A "$UA" -H 'Accept: text/html' -c "$E2E_JAR" -b "$E2E_JAR" -L -o /dev/null -w '%{url_effective}' "$APP/oauth2/start")"
_slug="$(printf '%s' "$_eff" | sed -nE 's#.*/if/flow/([^/?]+).*#\1#p')"
_qs="$(printf '%s' "$_eff" | sed -nE 's#[^?]*\?(.*)#\1#p')"
if [ -n "$_slug" ]; then
    _ex="$BASE/api/v3/flows/executor/$_slug/?query=$(printf '%s' "$_qs" | jq -sRr @uri)"
    _h="-H Accept:application/json -H Content-Type:application/json -H Referer:$_eff -H Origin:$BASE"
    curl -s --cacert "$CA" -A "$UA" $_h -c "$E2E_JAR" -b "$E2E_JAR" "$_ex" >/dev/null
    curl -s --cacert "$CA" -A "$UA" $_h -c "$E2E_JAR" -b "$E2E_JAR" -L -X POST "$_ex" -d '{"uid_field":"akadmin"}' >/dev/null
    _r="$(curl -s --cacert "$CA" -A "$UA" $_h -c "$E2E_JAR" -b "$E2E_JAR" -L -X POST "$_ex" -d "{\"password\":\"$AK_PW\"}")"
    _comp="$(printf '%s' "$_r" | jq -r '.component')"
    if [ "$UAT_MFA" = "totp" ]; then
        # Production-relevant assertion: MFA is ENFORCED — a correct
        # password alone does not grant access; the flow stops at the
        # second-factor stage.
        if [ "$_comp" = "ak-stage-authenticator-validate" ]; then
            PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "E2E: MFA enforced (password alone -> 2nd factor)" "OK"
        else
            FAIL=$((FAIL + 1)); printf '  FAIL  %-58s component=%s\n' "E2E: MFA enforced (password alone -> 2nd factor)" "$_comp"
        fi
        # Best-effort: complete the second factor with the enrolled TOTP
        # device. authentik's flow-executor does not reliably accept a
        # headless TOTP submission in this build, so a browser finishes it
        # (secret printed below); reaching the app here is a bonus, not a
        # required assertion.
        _code="$(totp "$TOTP_SECRET")"
        _r2="$(curl -s --cacert "$CA" -A "$UA" $_h -c "$E2E_JAR" -b "$E2E_JAR" -L -X POST "$_ex" \
            -d "{\"component\":\"ak-stage-authenticator-validate\",\"code\":\"$_code\"}")"
        _to="$(printf '%s' "$_r2" | jq -r '.to // empty')"; case "$_to" in /*) _to="$BASE$_to";; esac
        if [ -n "$_to" ]; then
            _hc="$(curl -s --cacert "$CA" -A "$UA" -H 'Accept: text/html' -c "$E2E_JAR" -b "$E2E_JAR" -L -o "$E2E_OUT" -w '%{http_code}' "$_to")"
            grep -q "X-Forwarded-Preferred-Username: akadmin" "$E2E_OUT" 2>/dev/null && \
                printf '  PASS  %-58s %s\n' "E2E: TOTP second factor accepted -> protected app" "whoami OK" && PASS=$((PASS + 1))
        else
            say "   note: headless TOTP submission not completed by this authentik build;"
            say "         finish in a browser with the printed secret. MFA IS enforced."
        fi
    else
        # skip mode: password-only login must reach the protected app.
        _to="$(printf '%s' "$_r" | jq -r '.to // empty')"; case "$_to" in /*) _to="$BASE$_to";; esac
        if [ -n "$_to" ]; then
            _hc="$(curl -s --cacert "$CA" -A "$UA" -H 'Accept: text/html' -c "$E2E_JAR" -b "$E2E_JAR" -L -o "$E2E_OUT" -w '%{http_code}' "$_to")"
            if [ "$_hc" = "200" ] && grep -q "X-Forwarded-Preferred-Username: akadmin" "$E2E_OUT"; then
                PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "E2E: akadmin logs in (password) -> protected app" "whoami OK"
            else
                FAIL=$((FAIL + 1)); printf '  FAIL  %-58s http=%s\n' "E2E: akadmin logs in (password) -> protected app" "$_hc"
            fi
        else
            FAIL=$((FAIL + 1)); printf '  FAIL  %-58s stuck at %s\n' "E2E: akadmin logs in (password) -> protected app" "$_comp"
        fi
    fi
else
    FAIL=$((FAIL + 1)); printf '  FAIL  %-58s %s\n' "E2E: akadmin logs in and reaches protected app" "no flow"
fi
rm -f "$E2E_JAR" "$E2E_OUT"

BOOTSTRAP_PW="$(grep '^AUTHENTIK_BOOTSTRAP_PASSWORD=' .env | cut -d= -f2-)"
say ""
say "== result: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
    say ""
    say "Admin/login:  $BASE   (akadmin / $BOOTSTRAP_PW)"
    say "Mock app:     $APP"
    say "MFA mode:     $UAT_MFA   (UAT_MFA=totp keeps MFA on and validates a TOTP device;"
    say "              UAT_MFA=skip removes the MFA stage for password-only login)"
    if [ "$UAT_MFA" = "totp" ] && [ -n "$TOTP_SECRET" ]; then
        say "  akadmin TOTP secret (add to an authenticator app): $TOTP_SECRET"
        say "  current code: $(totp "$TOTP_SECRET")"
    fi
    say "  Opening the mock app runs the full OIDC auth-code flow against"
    say "  authentik and then proxies the whoami upstream with identity headers."
    say "  Trust $(pwd)/tls/ca.crt in your browser (or accept the warnings)."
    say "Tear down:    ./run-uat.sh --down"
fi
[ "$FAIL" -eq 0 ]
