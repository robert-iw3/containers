#!/usr/bin/env bash
# Open (or replace) the end-user Boundary session to the dev portal and
# expose it on https://127.0.0.1:27007 for your browser. This is the ONLY
# ingress path to the portal — the session is brokered and audited by
# Boundary; TLS runs end to end from browser through the session to the
# portal proxy (expect the demo-CA trust prompt, or import .portal-ca.crt).
set -euo pipefail

cd "$(dirname "$0")/.."
RUNTIME="${RUNTIME:-podman}"
ADMIN_FILE=".boundary-admin.json"

[ -s "$ADMIN_FILE" ] || { echo "FAIL: $ADMIN_FILE missing — run scripts/smoke-test.sh once first"; exit 1; }
AUTH_METHOD_ID=$(grep -o '"auth_method_id":"[^"]*"' "$ADMIN_FILE" | cut -d'"' -f4)
LOGIN_NAME=$(grep -o '"login_name":"[^"]*"' "$ADMIN_FILE" | cut -d'"' -f4)
PASSWORD=$(grep -o '"password":"[^"]*"' "$ADMIN_FILE" | cut -d'"' -f4)

PORTAL_TARGET_ID=$("$RUNTIME" run --rm --user root -v backstage_portal-state:/portal-state:ro localhost/vault:2.0.3 \
  sh -c 'grep PORTAL_TARGET_ID /portal-state/boundary-ids.env | cut -d= -f2')
[ -n "$PORTAL_TARGET_ID" ] || { echo "FAIL: no portal target id recorded"; exit 1; }

echo "==> authenticating to Boundary as $LOGIN_NAME"
TOKEN=$("$RUNTIME" exec -e BOUNDARY_ADDR=https://127.0.0.1:9200 \
  -e BOUNDARY_CACERT=/portal-certs/ca.crt -e BPW="$PASSWORD" backstage-boundary \
  boundary authenticate password -auth-method-id "$AUTH_METHOD_ID" \
  -login-name "$LOGIN_NAME" -password env://BPW -keyring-type=none -format=json 2>/dev/null \
  | grep -o '"token": *"[^"]*"' | sed -n 1p | cut -d'"' -f4 || true)
[ -n "$TOKEN" ] || { echo "FAIL: boundary authentication failed"; exit 1; }

echo "==> replacing any previous session listener"
# bracketed pattern so pkill cannot match its own sh -c command line
"$RUNTIME" exec backstage-boundary sh -c 'pkill -f "boundary conn[e]ct" || true'

echo "==> opening supervised session to the dev portal target"
# supervised: the connect proxy can die (e.g. websocket corruption under
# heavy parallel connections); respawn it so 27007 never stays dead
"$RUNTIME" exec -d -e BOUNDARY_ADDR=https://127.0.0.1:9200 \
  -e BOUNDARY_CACERT=/portal-certs/ca.crt -e BT="$TOKEN" backstage-boundary \
  sh -c 'while true; do
    boundary connect -target-id '"$PORTAL_TARGET_ID"' -token env://BT \
      -listen-addr 0.0.0.0 -listen-port 27007
    echo "portal session listener exited; respawning in 2s"
    sleep 2
  done'

sleep 2
echo
echo "Dev portal session is live: https://127.0.0.1:27007"
echo "  SSO login:   portal-dev / PORTAL_DEV_PASSWORD from .env (via Keycloak)"
echo "  trust store: import ./.portal-ca.crt or accept the browser warning"
