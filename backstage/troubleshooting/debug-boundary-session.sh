#!/usr/bin/env bash
# Walk the end-user Boundary path step by step and show WHERE it breaks:
# admin auth -> target lookup -> worker/target reachability -> live session
# with the connect log captured (this is how the worker public_addr hairpin
# and the stale target-port bugs were found).
set -uo pipefail

cd "$(dirname "$0")/.."
RUNTIME="${RUNTIME:-podman}"
ADMIN_FILE=".boundary-admin.json"

echo "==> admin credentials"
if [ ! -s "$ADMIN_FILE" ]; then
  echo "    $ADMIN_FILE missing — parsing initial creds from boundary logs"
  LOGS=$("$RUNTIME" logs backstage-boundary 2>&1)
  AUTH_METHOD_ID=$(echo "$LOGS" | grep -oE 'ampw_[A-Za-z0-9]+' | sed -n 1p || true)
  LOGIN_NAME=$(echo "$LOGS" | awk '/Login Name:/ {print $NF; exit}' || true)
  PASSWORD=$(echo "$LOGS" | awk '/Password:/ {print $NF; exit}' || true)
  [ -n "$AUTH_METHOD_ID" ] && [ -n "$PASSWORD" ] || { echo "FAIL: no creds in logs (db reset? podman-compose down -v)"; exit 1; }
else
  AUTH_METHOD_ID=$(grep -o '"auth_method_id":"[^"]*"' "$ADMIN_FILE" | cut -d'"' -f4)
  LOGIN_NAME=$(grep -o '"login_name":"[^"]*"' "$ADMIN_FILE" | cut -d'"' -f4)
  PASSWORD=$(grep -o '"password":"[^"]*"' "$ADMIN_FILE" | cut -d'"' -f4)
fi
CUR=$("$RUNTIME" logs backstage-boundary 2>&1 | grep -oE 'ampw_[A-Za-z0-9]+' | sed -n 1p || true)
[ -n "$CUR" ] && [ "$CUR" != "$AUTH_METHOD_ID" ] \
  && echo "    WARNING: $ADMIN_FILE auth method ($AUTH_METHOD_ID) != live ($CUR) — stale file, delete it"

echo "==> authenticate"
TOKEN=$("$RUNTIME" exec -e BOUNDARY_ADDR=https://127.0.0.1:9200 \
  -e BOUNDARY_CACERT=/portal-certs/ca.crt -e BPW="$PASSWORD" backstage-boundary \
  boundary authenticate password -auth-method-id "$AUTH_METHOD_ID" \
  -login-name "$LOGIN_NAME" -password env://BPW -keyring-type=none -format=json 2>/dev/null \
  | grep -o '"token": *"[^"]*"' | sed -n 1p | cut -d'"' -f4 || true)
[ -n "$TOKEN" ] || { echo "FAIL: authentication rejected (stale password? delete $ADMIN_FILE and retry)"; exit 1; }
echo "    ok"

echo "==> recorded targets"
IDS=$("$RUNTIME" run --rm --user root -v backstage_portal-state:/s:ro localhost/vault:2.0.3 \
  cat /s/boundary-ids.env 2>/dev/null || true)
echo "$IDS" | sed 's/^/    /'
PT=$(echo "$IDS" | grep PORTAL_TARGET_ID | cut -d= -f2)
[ -n "$PT" ] || { echo "FAIL: no portal target recorded — podman start -a backstage-boundary-setup"; exit 1; }

echo "==> worker public_addr (must be reachable from where connect runs)"
"$RUNTIME" exec backstage-boundary sh -c \
  'grep -A1 public_addr /home/boundary/config.rendered.hcl 2>/dev/null | sed -n 1p' \
  || echo "    (rendered config not readable)"

echo "==> target backend reachable from the worker?"
"$RUNTIME" exec backstage-boundary sh -c \
  'wget -q -O- --ca-certificate=/portal-certs/ca.crt https://portal-proxy:8443/healthz >/dev/null' 2>/dev/null \
  && echo "    portal-proxy:8443 direct: OK" \
  || echo "    portal-proxy:8443 direct: UNREACHABLE (proxy down? firewall?)"

echo "==> live session test (connect log captured)"
BODY=$("$RUNTIME" exec -e BOUNDARY_ADDR=https://127.0.0.1:9200 \
  -e BOUNDARY_CACERT=/portal-certs/ca.crt -e BT="$TOKEN" backstage-boundary sh -c '
  boundary connect -target-id '"$PT"' -token env://BT \
    -listen-addr 127.0.0.1 -listen-port 27099 > /tmp/connect-debug.log 2>&1 &
  sleep 4
  wget -q -O- --ca-certificate=/portal-certs/ca.crt https://127.0.0.1:27099/healthz 2>/dev/null
  rc=$?
  # kill ONLY the debug session (port 27099) — a plain "boundary connect"
  # pattern would also kill the live end-user session on 27007
  pkill -f "listen-port 270[9]9" 2>/dev/null
  sleep 1
  echo; echo "--- connect log ---"; cat /tmp/connect-debug.log
  exit $rc' || true)
echo "$BODY" | sed 's/^/    /'
if [ "$(echo "$BODY" | grep -c '^ok')" -gt 0 ]; then
  echo "debug-boundary-session: SESSION WORKS"
else
  echo "debug-boundary-session: SESSION FAILED — read the connect log above:"
  echo "  'unable to connect to worker at ...' -> worker public_addr wrong for this network"
  echo "  'dial tcp ...:PORT refused'          -> target default port stale (update the target)"
fi
