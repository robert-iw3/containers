#!/usr/bin/env bash
# Smoke / UAT test for the Boundary stack.
# Captures the generated admin credentials from the db-init logs on first run
# (stored in .boundary-admin.json, chmod 600), authenticates, and lists scopes.
set -euo pipefail

cd "$(dirname "$0")/.."

RUNTIME="${RUNTIME:-podman}"
ADMIN_FILE=".boundary-admin.json"

echo "==> waiting for controller health endpoint"
for i in $(seq 1 60); do
  if "$RUNTIME" exec boundary-main wget -q -O- http://127.0.0.1:9203/health >/dev/null 2>&1; then
    break
  fi
  [ "$i" = 60 ] && { echo "FAIL: ops /health never responded"; exit 1; }
  sleep 2
done
echo "    /health OK"

if [ ! -s "$ADMIN_FILE" ]; then
  echo "==> extracting generated admin credentials from first-run logs"
  LOGS=$("$RUNTIME" logs boundary-main 2>&1)
  AUTH_METHOD_ID=$(echo "$LOGS" | grep -oE 'ampw_[A-Za-z0-9]+' | head -1 || true)
  LOGIN_NAME=$(echo "$LOGS" | awk '/Login Name:/ {print $NF; exit}' || true)
  PASSWORD=$(echo "$LOGS" | awk '/Password:/ {print $NF; exit}' || true)
  [ -n "$AUTH_METHOD_ID" ] && [ -n "$PASSWORD" ] || {
    echo "FAIL: could not parse admin credentials from boundary-main logs."
    echo "      The credentials are only printed on the first-ever database init."
    echo "      Either restore boundary/$ADMIN_FILE, or reset with:"
    echo "        podman-compose down -v && podman-compose up -d"
    exit 1
  }
  printf '{"auth_method_id":"%s","login_name":"%s","password":"%s"}\n' \
    "$AUTH_METHOD_ID" "$LOGIN_NAME" "$PASSWORD" > "$ADMIN_FILE"
  chmod 600 "$ADMIN_FILE"
  echo "    admin credentials written to boundary/$ADMIN_FILE (keep safe, UAT only)"
fi

AUTH_METHOD_ID=$(python3 -c "import json;print(json.load(open('$ADMIN_FILE'))['auth_method_id'])")
LOGIN_NAME=$(python3 -c "import json;print(json.load(open('$ADMIN_FILE'))['login_name'])")
PASSWORD=$(python3 -c "import json;print(json.load(open('$ADMIN_FILE'))['password'])")

echo "==> authenticating as $LOGIN_NAME"
TOKEN=$("$RUNTIME" exec -e BOUNDARY_ADDR=http://127.0.0.1:9200 -e BPW="$PASSWORD" boundary-main \
  boundary authenticate password -auth-method-id "$AUTH_METHOD_ID" \
  -login-name "$LOGIN_NAME" -password env://BPW -keyring-type=none -format=json \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['item']['attributes']['token'])")
[ -n "$TOKEN" ] || { echo "FAIL: authentication returned no token"; exit 1; }

echo "==> listing scopes"
"$RUNTIME" exec -e BOUNDARY_ADDR=http://127.0.0.1:9200 -e BOUNDARY_TOKEN="$TOKEN" boundary-main \
  boundary scopes list -token env://BOUNDARY_TOKEN

echo "==> listing targets in generated project scope"
"$RUNTIME" exec -e BOUNDARY_ADDR=http://127.0.0.1:9200 -e BOUNDARY_TOKEN="$TOKEN" boundary-main \
  boundary targets list -recursive -token env://BOUNDARY_TOKEN || true

echo
echo "PASS: Boundary controller/worker healthy, admin auth works."
echo "UI:       http://localhost:9200"
echo "Login:    $LOGIN_NAME / $PASSWORD  (auth method $AUTH_METHOD_ID)"
