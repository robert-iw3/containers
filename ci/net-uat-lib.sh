# Shared helpers for the networking stacks' UAT harnesses (coredns, the three
# reverse proxies, and the VPN stacks). Sourced — not executed — by each
# <stack>/uat/run-uat.sh.
#
# This is the SSO-free sibling of ci/sso-uat-lib.sh: the same primitives
# (say/pass/fail, check, wait_http, wait_healthy, up, gen_tls) without the
# tinyauth forwardAuth assertions, which don't apply to plain proxies, a DNS
# resolver, or a VPN gateway. The devops SSO stacks keep using sso-uat-lib.sh.
#
# A caller sets, before sourcing then calling net_init:
#   STACK         short stack name, e.g. traefik
#   COMPOSE_FILE  compose file to drive (default ../docker-compose.yml)
#   CERT_CN       certificate common name (optional; enables gen_tls)
#   CERT_SANS     space-separated SAN hosts for the certificate (optional)
# and after net_init runs the check_* assertions, then net_report.

PASS=0
FAIL=0

say() { printf '%s\n' "$*"; }

pass() { PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "$1" "${2:-OK}"; }
fail() { FAIL=$((FAIL + 1)); printf '  FAIL  %-58s %s\n' "$1" "${2:-}"; }

# A real browser UA — some upstreams and middlewares treat empty/robot UAs
# differently (repo convention: always present as a browser on HTTP checks).
UA="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

# check <expected_code> <description> [curl args...]
check() {
    _want="$1"; _desc="$2"; shift 2
    _got="$(curl -s -o /dev/null -w '%{http_code}' -A "$UA" --max-time 30 "$@")"
    [ "$_got" = "$_want" ] && pass "$_desc" "$_got" || fail "$_desc" "got $_got want $_want"
}

# check_any <expected_codes_regex> <description> [curl args...]
check_any() {
    _re="$1"; _desc="$2"; shift 2
    _got="$(curl -s -o /dev/null -w '%{http_code}' -A "$UA" --max-time 30 "$@")"
    printf '%s' "$_got" | grep -qE "$_re" \
        && pass "$_desc" "$_got" || fail "$_desc" "got $_got want $_re"
}

# check_body <needle> <description> [curl args...] — body must contain needle.
check_body() {
    _needle="$1"; _desc="$2"; shift 2
    _body="$(curl -s -A "$UA" --max-time 30 "$@")"
    printf '%s' "$_body" | grep -qF "$_needle" \
        && pass "$_desc" || fail "$_desc" "$(printf '%s' "$_body" | head -c 120)"
}

# wait_http <url> <seconds> <accept-codes-regex> [curl args...]
wait_http() {
    _u="$1"; _t="$2"; _re="$3"; shift 3
    _i=0
    while [ "$_i" -lt "$_t" ]; do
        _code="$(curl -s -o /dev/null -w '%{http_code}' -A "$UA" --max-time 10 "$@" "$_u" 2>/dev/null)"
        printf '%s' "$_code" | grep -qE "$_re" && return 0
        _i=$((_i + 3)); sleep 3
    done
    say "!! $_u not answering ($_re) after $_t s (last: ${_code:-none})"
    return 1
}

# wait_healthy <container> <seconds> — gate between bring-up stages. Containers
# with no healthcheck pass as soon as they report running.
wait_healthy() {
    _c="$1"; _t="${2:-180}"; _i=0
    while [ "$_i" -lt "$_t" ]; do
        _s="$($RUNTIME inspect -f '{{.State.Health.Status}}' "$_c" 2>/dev/null || echo missing)"
        [ "$_s" = "healthy" ] && return 0
        if [ -z "$_s" ]; then
            [ "$($RUNTIME inspect -f '{{.State.Running}}' "$_c" 2>/dev/null)" = "true" ] && return 0
        fi
        _i=$((_i + 3)); sleep 3
    done
    say "!! $_c not healthy after $_t s (last: ${_s:-none})"
    return 1
}

# up <service...> — bring services up without recreating live containers.
# podman-compose recreates dependent chains when invoked broadly, so each
# stage names its services explicitly (see podman-compose-orchestration-hazards).
up() {
    $COMPOSE up -d --no-recreate "$@"
}

# ensure_running <container> — restart a container left stopped by a previous
# partial run (podman-compose cannot adopt those).
ensure_running() {
    _c="$1"
    [ "$($RUNTIME inspect -f '{{.State.Running}}' "$_c" 2>/dev/null)" = "true" ] && return 0
    $RUNTIME start "$_c" >/dev/null 2>&1 || true
}

# dumplog <container> [lines] — indent a container's tail into the report.
dumplog() {
    $RUNTIME logs --tail "${2:-30}" "$1" 2>&1 | sed 's/^/     /'
}

# ensure_stable <container> [seconds] — guard against crash loops. Watches the
# container briefly; if it exits (or is restart-looping), STOP it so it cannot
# keep churning the machine, dump its tail, and fail. Use right after `up` for
# any service that has ever crash-looped.
ensure_stable() {
    _c="$1"; _t="${2:-12}"; _i=0
    while [ "$_i" -lt "$_t" ]; do
        _st="$($RUNTIME inspect -f '{{.State.Status}}' "$_c" 2>/dev/null)"
        _rc="$($RUNTIME inspect -f '{{.RestartCount}}' "$_c" 2>/dev/null)"
        if [ "$_st" = "exited" ] || [ "${_rc:-0}" -gt 2 ] 2>/dev/null; then
            say "!! $_c is crash-looping (status=$_st restarts=${_rc:-?}); stopping it"
            $RUNTIME stop -t 2 "$_c" >/dev/null 2>&1 || true
            dumplog "$_c" 15
            return 1
        fi
        _i=$((_i + 3)); sleep 3
    done
    return 0
}

# gen_tls — local CA plus one server certificate into uat/tls. Enabled when the
# caller sets CERT_CN. The key is world readable: rootless podman maps container
# uids into the user namespace, so a 0600 host file is unreadable to the
# container's uid.
gen_tls() {
    [ -n "${CERT_CN:-}" ] || return 0
    [ -f tls/ca.crt ] && { chmod 644 tls/tls.key tls/tls.crt tls/ca.crt; return 0; }
    say "-- generating TLS CA + cert into uat/tls (CN=$CERT_CN)"
    mkdir -p tls
    openssl genrsa -out tls/ca.key 4096 2>/dev/null
    openssl req -x509 -new -nodes -key tls/ca.key -sha256 -days 3650 \
        -out tls/ca.crt -subj "/CN=$STACK UAT CA" 2>/dev/null
    _san="subjectAltName=DNS:$CERT_CN,DNS:localhost,IP:127.0.0.1"
    for _h in ${CERT_SANS:-}; do _san="$_san,DNS:$_h"; done
    openssl genrsa -out tls/tls.key 2048 2>/dev/null
    openssl req -new -key tls/tls.key -out tls/tls.csr \
        -subj "/CN=$CERT_CN" -addext "$_san" 2>/dev/null
    openssl x509 -req -in tls/tls.csr -CA tls/ca.crt -CAkey tls/ca.key \
        -CAcreateserial -out tls/tls.crt -days 365 -sha256 \
        -extfile /dev/stdin 2>/dev/null <<EOF
$_san
EOF
    chmod 644 tls/tls.key tls/tls.crt tls/ca.crt
}

# net_init — resolve the runtime, compose command and TLS material. Each stack
# writes its own uat/.env before calling this (their env shapes differ too much
# to share). Set SKIP_ENV_CHECK=1 to allow a missing .env.
net_init() {
    RUNTIME="${RUNTIME:-podman}"
    COMPOSE_BIN="${COMPOSE_BIN:-podman-compose}"
    COMPOSE_FILE="${COMPOSE_FILE:-../docker-compose.yml}"
    # podman-compose resolves a relative -f against a shifting cwd; pin it.
    COMPOSE_FILE="$(realpath "$COMPOSE_FILE" 2>/dev/null || echo "$COMPOSE_FILE")"
    PROJECT="${PROJECT:-${STACK}-net-uat}"
    if [ -f .env ]; then
        COMPOSE="$COMPOSE_BIN -p $PROJECT --env-file .env -f $COMPOSE_FILE"
    else
        COMPOSE="$COMPOSE_BIN -p $PROJECT -f $COMPOSE_FILE"
    fi
    CA=tls/ca.crt
    gen_tls
}

# net_down — tear the project and generated state down.
net_down() {
    RUNTIME="${RUNTIME:-podman}"
    COMPOSE_BIN="${COMPOSE_BIN:-podman-compose}"
    COMPOSE_FILE="${COMPOSE_FILE:-../docker-compose.yml}"
    COMPOSE_FILE="$(realpath "$COMPOSE_FILE" 2>/dev/null || echo "$COMPOSE_FILE")"
    PROJECT="${PROJECT:-${STACK}-net-uat}"
    if [ -f .env ]; then
        $COMPOSE_BIN -p "$PROJECT" --env-file .env -f "$COMPOSE_FILE" down -v 2>/dev/null
    else
        $COMPOSE_BIN -p "$PROJECT" -f "$COMPOSE_FILE" down -v 2>/dev/null
    fi
    rm -rf tls .env
}

# net_report — print the tally; return non-zero on any failure.
net_report() {
    say ""
    say "== result: $PASS passed, $FAIL failed"
    [ "$FAIL" -eq 0 ]
}
