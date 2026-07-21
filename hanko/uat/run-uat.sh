#!/bin/sh
# UAT / smoke test for the Hanko stack — TLS end to end.
#
#   ./run-uat.sh [--down]
#
# Runs Hanko (native TLS) + PostgreSQL (TLS) + mailslurper + a TLS login
# page on localhost, waits for readiness, asserts the API surface and
# that /me enforces authentication. The stack stays up for manual login;
# --down tears it down.
set -u

cd "$(dirname "$0")"

COMPOSE_BIN="${COMPOSE:-podman-compose}"
COMPOSE="$COMPOSE_BIN -p hanko-uat -f docker-compose.uat.yml"
API=https://localhost:8000
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

if [ "${1:-}" = "--down" ]; then
    $COMPOSE down -v
    exit 0
fi

say "== hanko UAT (TLS)"

if [ ! -f .env ]; then
    say "-- generating uat/.env credentials"
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 20)" > .env
fi

if [ ! -f "$CA" ]; then
    say "-- generating TLS CA + certs into uat/tls"
    ../generate-tls.sh >/dev/null 2>&1 || { say "!! generate-tls.sh failed"; exit 1; }
fi
# nginx (uid 101) and hanko (nonroot) must read the key across the
# rootless userns; postgres keeps its own 0600 copy internally.
chmod 644 tls/tls.key tls/tls.crt tls/ca.crt

if [ ! -f config-uat.yml ]; then
    say "-- rendering config-uat.yml"
    PG_PW="$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)"
    sed -e "s|__PG_PASSWORD__|$PG_PW|" \
        -e "s|__JWT_KEY__|$(openssl rand -hex 32)|" \
        config-uat.yml.tmpl > config-uat.yml
fi

# Staged bring-up with --no-recreate: podman-compose's dependency engine
# is unreliable with one-shots, so this script owns the ordering.
say "-- starting postgres"
$COMPOSE up -d --no-recreate postgres || exit 1
wait_healthy postgres-hanko-uat 120 || exit 1

say "-- running migrations"
$COMPOSE up -d --no-recreate hanko-migrate || exit 1
_i=0
while [ "$_i" -lt 90 ]; do
    _state="$(podman inspect --format '{{.State.Status}} {{.State.ExitCode}}' hanko-uat_hanko-migrate_1 2>/dev/null)"
    case "$_state" in
        "exited 0") break ;;
        exited*) say "!! migration failed: $_state"
                 podman logs --tail 20 hanko-uat_hanko-migrate_1 2>&1 | sed 's/^/     /'
                 exit 1 ;;
    esac
    _i=$((_i + 2)); sleep 2
done
[ "$_i" -ge 90 ] && { say "!! migration did not finish in 90 s"; exit 1; }

say "-- starting hanko, tls proxy, mailslurper"
$COMPOSE up -d --no-recreate hanko proxy mailslurper || exit 1
wait_http "$API/.well-known/jwks.json" 120 --cacert "$CA" || {
    podman logs --tail 20 hanko-uat 2>&1 | sed 's/^/     /'
    podman logs --tail 10 hanko-proxy-uat 2>&1 | sed 's/^/     /'; exit 1;
}

say "== checks"
check 200 "JWKS endpoint (TLS)"       --cacert "$CA" "$API/.well-known/jwks.json"
check 200 "well-known config (TLS)"   --cacert "$CA" "$API/.well-known/config"
check 401 "/me requires auth"         --cacert "$CA" "$API/me"
check 200 "login page (TLS)"          --cacert "$CA" https://localhost:8888/
check 200 "mailslurper UI"            http://127.0.0.1:8086/

# --- Full end-to-end registration + login (browser User-Agent) ------------
# Drive Hanko's real flow API the way the login page does: register a new
# user (email -> passcode read from mailslurper -> password -> skip MFA),
# then call /me with the resulting session cookie and assert it returns the
# registered user. Proves the whole chain incl. SMTP passcode delivery.
say "-- end-to-end registration + login (browser UA, passcode via mailslurper)"
UA="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
E2E_JAR="$(mktemp)"
_post(){ curl -s --cacert "$CA" -A "$UA" -c "$E2E_JAR" -b "$E2E_JAR" -H 'Content-Type: application/json' -X POST "$API$1" -d "$2"; }
_href(){ printf '%s' "$1" | jq -r ".actions.$2.href"; }
_csrf(){ printf '%s' "$1" | jq -r '.csrf_token'; }
E2E_EMAIL="uat-e2e-$(date +%s)@uat.local"
E2E_PW="HankoE2E-$(openssl rand -hex 4)!"
r="$(_post /registration '{}')"
r="$(_post "$(_href "$r" register_client_capabilities)" "{\"csrf_token\":\"$(_csrf "$r")\",\"input_data\":{\"webauthn_available\":false,\"webauthn_conditional_mediation_available\":false,\"webauthn_platform_authenticator_available\":false}}")"
r="$(_post "$(_href "$r" register_login_identifier)" "{\"csrf_token\":\"$(_csrf "$r")\",\"input_data\":{\"email\":\"$E2E_EMAIL\"}}")"
sleep 2
code="$(curl -s http://127.0.0.1:8086/mail 2>/dev/null | jq -r '.mailItems|sort_by(.dateSent)|last|.body' 2>/dev/null | grep -oiE '[0-9]{6}' | head -1)"
[ -z "$code" ] && code="$(curl -s http://127.0.0.1:8087/mail 2>/dev/null | jq -r '.mailItems|sort_by(.dateSent)|last|.body' 2>/dev/null | grep -oiE '[0-9]{6}' | head -1)"
r="$(_post "$(_href "$r" verify_passcode)" "{\"csrf_token\":\"$(_csrf "$r")\",\"input_data\":{\"code\":\"$code\"}}")"
r="$(_post "$(_href "$r" register_password)" "{\"csrf_token\":\"$(_csrf "$r")\",\"input_data\":{\"new_password\":\"$E2E_PW\"}}")"
# The optional MFA-method chooser only appears in some builds; skip if present.
if printf '%s' "$r" | jq -e '.actions.skip' >/dev/null 2>&1; then
    r="$(_post "$(_href "$r" skip)" "{\"csrf_token\":\"$(_csrf "$r")\"}")"
fi
FINAL_STATE="$(printf '%s' "$r" | jq -r '.name')"
ME_EMAIL="$(curl -s --cacert "$CA" -A "$UA" -b "$E2E_JAR" "$API/me" | jq -r '.emails[0].address // empty' 2>/dev/null)"
if [ "$FINAL_STATE" = "success" ] && [ "$ME_EMAIL" = "$E2E_EMAIL" ]; then
    PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "E2E: register -> passcode -> session -> /me" "$ME_EMAIL"
else
    FAIL=$((FAIL + 1)); printf '  FAIL  %-58s state=%s me=%s\n' "E2E: register -> passcode -> session -> /me" "$FINAL_STATE" "$ME_EMAIL"
fi
rm -f "$E2E_JAR"

say ""
say "== result: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
    say ""
    say "Log in at:  https://localhost:8888"
    say "  1. visit https://localhost:8000/health/alive once and accept the cert"
    say "     (or trust $(pwd)/tls/ca.crt in your browser)"
    say "  2. register any e-mail — passcode arrives in http://localhost:8086 —"
    say "     or use password auth; the page then calls /me to prove integration"
    say "Tear down:  ./run-uat.sh --down"
fi
[ "$FAIL" -eq 0 ]
