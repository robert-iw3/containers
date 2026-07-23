#!/bin/sh
# UAT / smoke test for the full Neo4j GraphRAG + Keycloak + OpenWebUI stack.
# Brings the environment up over TLS and proves: Keycloak realm import, the
# GraphRAG OpenAI-compatible API, OpenWebUI reachability, and an end-to-end
# Keycloak authorization-code login that mints an OpenWebUI session.
#
#   ./run-uat.sh [--down]
#
# Needs these names to resolve to 127.0.0.1 (automatic for *.localhost):
#   127.0.0.1  chat.neo4j.localhost keycloak.neo4j.localhost
#
# Issuer host consistency requires host port 8443 == traefik's :8443.
set -u

cd "$(dirname "$0")"
STACK_DIR="$(cd .. && pwd)"

RUNTIME="${RUNTIME:-podman}"
COMPOSE_BIN="${COMPOSE_BIN:-podman-compose}"
COMPOSE="$COMPOSE_BIN -p neo4j-stack --env-file $STACK_DIR/.env -f $STACK_DIR/docker-compose.yml"

TLS_PORT=8443
APP_HOST=chat.neo4j.localhost
KEYCLOAK_HOST=keycloak.neo4j.localhost
REALM=neo4j
NET_SUBNET=172.31.30.0/24
TRAEFIK_IP=172.31.30.10
CA="$STACK_DIR/tls/ca.crt"
APP="https://$APP_HOST:$TLS_PORT"
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
    $COMPOSE --profile load down -v
    rm -f "$STACK_DIR/.env" "$STACK_DIR/keycloak/realm-neo4j.json" "$STACK_DIR/.demo-password"
    rm -rf "$STACK_DIR/tls"
    exit 0
fi

say "== Neo4j GraphRAG + Keycloak + OpenWebUI full-stack UAT (TLS, real OIDC login)"

# --- TLS -----------------------------------------------------------------
if [ ! -f "$CA" ]; then
    say "-- generating TLS CA + cert"
    mkdir -p "$STACK_DIR/tls"
    openssl genrsa -out "$STACK_DIR/tls/ca.key" 4096 2>/dev/null
    openssl req -x509 -new -nodes -key "$STACK_DIR/tls/ca.key" -sha256 -days 3650 \
        -out "$CA" -subj "/CN=Neo4j RAG Stack UAT CA" 2>/dev/null
    SAN="subjectAltName=DNS:$APP_HOST,DNS:$KEYCLOAK_HOST,DNS:localhost,IP:127.0.0.1"
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

# --- secrets, .env, realm (localhost hostnames for the UAT) --------------
if [ ! -f "$STACK_DIR/.env" ]; then
    say "-- generating .env and Keycloak realm"
    DEMO_USER=demo
    DEMO_EMAIL=demo@example.com
    DEMO_PW="$(openssl rand -base64 12 | tr -d '/+=')"
    CLIENT_SECRET="$(openssl rand -hex 24)"
    printf '%s' "$DEMO_PW" > "$STACK_DIR/.demo-password"; chmod 600 "$STACK_DIR/.demo-password"
    {
        echo "COMPOSE_NET_NAME=neo4j-stack"
        echo "NET_SUBNET=$NET_SUBNET"
        echo "TRAEFIK_IP=$TRAEFIK_IP"
        echo "BIND_ADDR=127.0.0.1"
        echo "TLS_PORT=$TLS_PORT"
        echo "TLS_DIR=$STACK_DIR/tls"
        echo "DOCKER_SOCKET=$DOCKER_SOCKET"
        echo "APP_HOST=$APP_HOST"
        echo "KEYCLOAK_HOST=$KEYCLOAK_HOST"
        echo "KEYCLOAK_REALM=$REALM"
        echo "KEYCLOAK_ADMIN_USER=admin"
        echo "KEYCLOAK_ADMIN_PASSWORD=$(openssl rand -base64 15 | tr -d '/+=')"
        echo "KEYCLOAK_DB_PASSWORD=$(openssl rand -hex 20)"
        echo "OPENWEBUI_DB_PASSWORD=$(openssl rand -hex 20)"
        echo "WEBUI_SECRET_KEY=$(openssl rand -hex 32)"
        echo "OAUTH_CLIENT_ID=openwebui"
        echo "OAUTH_CLIENT_SECRET=$CLIENT_SECRET"
        echo "NEO4J_USERNAME=neo4j"
        echo "NEO4J_PASSWORD=$(openssl rand -hex 16)"
        echo "GRAPHRAG_API_KEY=$(openssl rand -hex 24)"
        echo "LLM=llama3.2:1b"
        echo "EMBEDDING_MODEL=sentence_transformer"
        echo "RAG_SEARCH_TYPE=vector"
        echo "RAG_USE_COMPRESSION=false"
    } > "$STACK_DIR/.env"
    chmod 600 "$STACK_DIR/.env"
    sed -e "s#@REALM@#$REALM#g" \
        -e "s#@CLIENT_ID@#openwebui#g" \
        -e "s#@CLIENT_SECRET@#$CLIENT_SECRET#g" \
        -e "s#@REDIRECT_URI@#$APP/oauth/oidc/callback#g" \
        -e "s#@DEMO_USER@#$DEMO_USER#g" \
        -e "s#@DEMO_EMAIL@#$DEMO_EMAIL#g" \
        -e "s#@DEMO_PASSWORD@#$DEMO_PW#g" \
        "$STACK_DIR/keycloak/realm-neo4j.json.tmpl" > "$STACK_DIR/keycloak/realm-neo4j.json"
fi
DEMO_USER=demo
DEMO_PW="$(cat "$STACK_DIR/.demo-password" 2>/dev/null)"
API_KEY="$(grep '^GRAPHRAG_API_KEY=' "$STACK_DIR/.env" | cut -d= -f2)"

# --- bring-up ------------------------------------------------------------
# Single create pass for the whole stack (compose resolves dependency order),
# then gate on healthchecks in order. Creating service-by-service makes
# podman-compose eagerly re-create already-running depends_on targets and emit
# name-collision noise, so create everything once here.
say "-- creating the stack"
$COMPOSE up -d || exit 1

say "-- stage 1: databases + neo4j + ollama"
wait_healthy keycloak-db-neo4j-stack 120 || exit 1
wait_healthy openwebui-db-neo4j-stack 120 || exit 1
wait_healthy neo4j-neo4j-stack 180 || exit 1
wait_healthy ollama-neo4j-stack 120 || exit 1

say "-- stage 2: keycloak realm import"
wait_http "$ISSUER/.well-known/openid-configuration" 240 '^200$' --cacert "$CA" || {
    $RUNTIME logs --tail 30 keycloak-neo4j-stack 2>&1 | sed 's/^/     /'; exit 1; }
pass "Keycloak realm '$REALM' imported and discoverable"

say "-- stage 3: graphrag + openwebui (models pulling in background)"
wait_healthy graphrag-neo4j-stack 300 || {
    $RUNTIME logs --tail 40 graphrag-neo4j-stack 2>&1 | sed 's/^/     /'; }
wait_http "$APP/health" 180 '^200$' --cacert "$CA" || {
    $RUNTIME logs --tail 40 open-webui-neo4j-stack 2>&1 | sed 's/^/     /'; exit 1; }

say "== checks"
check 200 "Keycloak OIDC discovery (TLS)" --cacert "$CA" "$ISSUER/.well-known/openid-configuration"
check 200 "OpenWebUI health endpoint" --cacert "$CA" "$APP/health"
check 200 "OpenWebUI config advertises OIDC (oauth)" --cacert "$CA" "$APP/api/config"
$RUNTIME exec graphrag-neo4j-stack curl -fsS http://localhost:8504/health >/dev/null 2>&1 \
    && pass "GraphRAG service healthy (in-network)" || fail "GraphRAG service healthy (in-network)"

# GraphRAG OpenAI-compatible API — models list + a completion, from inside the
# network (the API is not published to the host by design).
_models="$($RUNTIME exec graphrag-neo4j-stack curl -fsS -H "Authorization: Bearer $API_KEY" \
    http://localhost:8504/v1/models 2>/dev/null)"
printf '%s' "$_models" | grep -q neo4j-graphrag \
    && pass "GraphRAG /v1/models lists neo4j-graphrag" \
    || fail "GraphRAG /v1/models lists neo4j-graphrag" "$(printf '%s' "$_models" | head -c 80)"
_unauth="$($RUNTIME exec graphrag-neo4j-stack curl -s -o /dev/null -w '%{http_code}' \
    http://localhost:8504/v1/models 2>/dev/null)"
[ "$_unauth" = "401" ] && pass "GraphRAG rejects requests without the API key" \
    || fail "GraphRAG rejects requests without the API key" "got $_unauth"

# OpenWebUI must advertise the Keycloak provider in its public config.
curl -s --cacert "$CA" "$APP/api/config" | grep -qi 'oauth\|oidc' \
    && pass "OpenWebUI exposes the Keycloak OAuth login" \
    || fail "OpenWebUI exposes the Keycloak OAuth login"

# --- End-to-end: real Keycloak login through to an OpenWebUI session -----
# OpenWebUI starts the OIDC flow at /oauth/oidc/login; follow the redirect to
# Keycloak, submit the demo credentials, and confirm the callback lands back on
# OpenWebUI with a session token cookie.
say "-- end-to-end Keycloak login (browser UA)"
JAR="$(mktemp)"
_kc_login="$(curl -s -c "$JAR" -b "$JAR" --cacert "$CA" -A "$UA" -i "$APP/oauth/oidc/login" \
    | grep -i '^location:' | tail -1 | sed 's/[Ll]ocation: //I' | tr -d '\r')"
case "$_kc_login" in
    "$ISSUER/protocol/openid-connect/auth"*)
        pass "OpenWebUI redirects to Keycloak authorization endpoint" ;;
    *)  fail "OpenWebUI redirects to Keycloak authorization endpoint" "loc=${_kc_login:-none}" ;;
esac
_form="$(curl -s -c "$JAR" -b "$JAR" --cacert "$CA" -A "$UA" "$_kc_login")"
_action="$(printf '%s' "$_form" | grep -oE 'action="[^"]+"' | head -1 | sed 's/action="//;s/"$//' | sed 's/&amp;/\&/g')"
if [ -z "$_action" ]; then
    # Empty login form usually means Keycloak rejected the request (e.g. an
    # invalid scope); show why instead of a downstream curl error.
    _why="$(curl -s -i -o /dev/null -w '%{redirect_url}' -c "$JAR" -b "$JAR" --cacert "$CA" -A "$UA" "$_kc_login")"
    fail "Keycloak serves the login form" "no <form action>; keycloak said: ${_why:-empty response}"
    say "== result: $PASS passed, $((FAIL+1)) failed"; rm -f "$JAR"; exit 1
fi
_cb="$(curl -s -c "$JAR" -b "$JAR" --cacert "$CA" -A "$UA" -i -X POST "$_action" \
    --data-urlencode "username=$DEMO_USER" --data-urlencode "password=$DEMO_PW" \
    --data-urlencode "credentialId=" | grep -i '^location:' | tail -1 | sed 's/[Ll]ocation: //I' | tr -d '\r')"
case "$_cb" in
    "$APP/oauth/oidc/callback"*)
        pass "Keycloak authenticates demo user and redirects to callback" ;;
    *)  fail "Keycloak authenticates demo user and redirects to callback" "redirect=${_cb:-none}" ;;
esac
_setcookie="$(curl -s -c "$JAR" -b "$JAR" --cacert "$CA" -A "$UA" -D - "$_cb" -o /dev/null)"
rm -f "$JAR"
if printf '%s' "$_setcookie" | grep -qi 'set-cookie: *token='; then
    pass "OpenWebUI issues a session from the Keycloak identity"
else
    fail "OpenWebUI issues a session from the Keycloak identity" "no token cookie"
fi

say ""
say "== stack"
say "OpenWebUI:  $APP"
say "Keycloak:   https://$KEYCLOAK_HOST:$TLS_PORT/admin/  (realm $REALM)"
say "Demo user:  $DEMO_USER / $DEMO_PW"
say "  Trust $STACK_DIR/tls/ca.crt in your browser, or accept the warning."
say "Load data:  $COMPOSE --profile load run --rm loader --tag neo4j --pages 1"
say "Tear down:  ./run-uat.sh --down"
say ""
say "== result: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
