#!/usr/bin/env bash
# End-to-end smoke / UAT for the HashiCorp stack demo:
#   1. Consul: leader, catalog contains vault/postgres-app/demo-api, mesh
#      intentions allow demo-api -> postgres-app and deny others
#   2. Vault: initialized + unsealed, database engine issues creds
#   3. demo-api: serves data fetched over the mesh with a Vault-issued DB user
#   4. Boundary: admin auth, authorize-session on the postgres target returns
#      brokered Vault credentials, and those credentials actually work
set -euo pipefail

cd "$(dirname "$0")/.."

RUNTIME="${RUNTIME:-podman}"
ADMIN_FILE=".boundary-admin.json"
fail() { echo "FAIL: $*"; exit 1; }

echo "==> [consul] waiting for leader"
for i in $(seq 1 60); do
  LEADER=$("$RUNTIME" exec demo-consul curl -sf http://127.0.0.1:8500/v1/status/leader 2>/dev/null || true)
  [ -n "$LEADER" ] && [ "$LEADER" != '""' ] && break
  [ "$i" = 60 ] && fail "no consul leader"
  sleep 2
done

echo "==> [vault] waiting for vault-setup to finish"
for i in $(seq 1 120); do
  "$RUNTIME" logs demo-vault-setup 2>&1 | grep -q 'vault-setup: DONE' && break
  "$RUNTIME" logs demo-vault-setup 2>&1 | grep -q '^FAIL' && { "$RUNTIME" logs demo-vault-setup | tail -5; fail "vault-setup failed"; }
  [ "$i" = 120 ] && { "$RUNTIME" logs demo-vault-setup | tail -10; fail "vault-setup never finished"; }
  sleep 2
done
echo "    vault-setup complete"

echo "==> [boundary] waiting for boundary-setup to finish"
for i in $(seq 1 120); do
  "$RUNTIME" logs demo-boundary-setup 2>&1 | grep -q 'boundary-setup: DONE\|already configured' && break
  [ "$i" = 120 ] && { "$RUNTIME" logs demo-boundary-setup | tail -10; fail "boundary-setup never finished"; }
  sleep 2
done
echo "    boundary-setup complete"

echo "==> [consul] catalog services"
SERVICES=$("$RUNTIME" exec demo-consul curl -sf http://127.0.0.1:8500/v1/catalog/services)
echo "    $SERVICES"
for svc in vault postgres-app demo-api; do
  echo "$SERVICES" | grep -q "\"$svc\"" || fail "$svc not in consul catalog"
done

echo "==> [consul] mesh intentions"
ALLOW=$("$RUNTIME" exec demo-consul curl -sf "http://127.0.0.1:8500/v1/connect/intentions/check?source=demo-api&destination=postgres-app")
echo "$ALLOW" | grep -q '"Allowed": *true' || fail "intention demo-api -> postgres-app should be allowed: $ALLOW"
DENY=$("$RUNTIME" exec demo-consul curl -sf "http://127.0.0.1:8500/v1/connect/intentions/check?source=some-other-svc&destination=postgres-app")
echo "$DENY" | grep -q '"Allowed": *false' || fail "intention some-other-svc -> postgres-app should be denied: $DENY"
echo "    allow demo-api->postgres-app, deny *->postgres-app: OK"

echo "==> [demo-api] request through mesh with Vault-issued creds"
for i in $(seq 1 60); do
  BODY=$(curl -sf http://localhost:18080/ 2>/dev/null || true)
  echo "$BODY" | grep -q '"status": *"ok"' && break
  [ "$i" = 60 ] && { echo "$BODY"; "$RUNTIME" logs --tail 5 demo-api; fail "demo-api never returned ok"; }
  sleep 2
done
echo "$BODY"
DB_USER=$(echo "$BODY" | grep -o '"db_user_from_vault": *"[^"]*"' | cut -d'"' -f4)
case "$DB_USER" in
  v-*) echo "    vault-issued dynamic user confirmed: $DB_USER" ;;
  *) fail "db user '$DB_USER' does not look vault-issued" ;;
esac

echo "==> [boundary] admin auth + brokered credentials"
if [ ! -s "$ADMIN_FILE" ]; then
  LOGS=$("$RUNTIME" logs demo-boundary 2>&1)
  AUTH_METHOD_ID=$(echo "$LOGS" | grep -oE 'ampw_[A-Za-z0-9]+' | head -1 || true)
  LOGIN_NAME=$(echo "$LOGS" | awk '/Login Name:/ {print $NF; exit}' || true)
  PASSWORD=$(echo "$LOGS" | awk '/Password:/ {print $NF; exit}' || true)
  [ -n "$AUTH_METHOD_ID" ] && [ -n "$PASSWORD" ] || fail "could not parse boundary admin creds (reset with: podman-compose down -v)"
  printf '{"auth_method_id":"%s","login_name":"%s","password":"%s"}\n' \
    "$AUTH_METHOD_ID" "$LOGIN_NAME" "$PASSWORD" > "$ADMIN_FILE"
  chmod 600 "$ADMIN_FILE"
fi
AUTH_METHOD_ID=$(grep -o '"auth_method_id":"[^"]*"' "$ADMIN_FILE" | cut -d'"' -f4)
LOGIN_NAME=$(grep -o '"login_name":"[^"]*"' "$ADMIN_FILE" | cut -d'"' -f4)
PASSWORD=$(grep -o '"password":"[^"]*"' "$ADMIN_FILE" | cut -d'"' -f4)

TOKEN=$("$RUNTIME" exec -e BOUNDARY_ADDR=http://127.0.0.1:9200 -e BPW="$PASSWORD" demo-boundary \
  boundary authenticate password -auth-method-id "$AUTH_METHOD_ID" \
  -login-name "$LOGIN_NAME" -password env://BPW -keyring-type=none -format=json 2>/dev/null \
  | grep -o '"token": *"[^"]*"' | head -1 | cut -d'"' -f4)
[ -n "$TOKEN" ] || fail "boundary authentication failed"
echo "    admin authenticated"

TARGET_ID=$("$RUNTIME" exec demo-boundary-setup cat /demo-state/boundary-ids.env 2>/dev/null \
  | grep TARGET_ID | cut -d= -f2 || true)
if [ -z "$TARGET_ID" ]; then
  TARGET_ID=$("$RUNTIME" run --rm -v hashicorp-stack_demo-state:/demo-state:ro localhost/vault:2.0.3 \
    sh -c 'grep TARGET_ID /demo-state/boundary-ids.env | cut -d= -f2')
fi
[ -n "$TARGET_ID" ] || fail "no TARGET_ID recorded by boundary-setup"

SESSION=$("$RUNTIME" exec -e BOUNDARY_ADDR=http://127.0.0.1:9200 -e BOUNDARY_TOKEN="$TOKEN" demo-boundary \
  boundary targets authorize-session -id "$TARGET_ID" -token env://BOUNDARY_TOKEN -format=json)
BROKERED_USER=$(echo "$SESSION" | grep -o '"username": *"v-[^"]*"' | head -1 | cut -d'"' -f4)
BROKERED_PASS=$(echo "$SESSION" | grep -o '"password": *"[^"]*"' | head -1 | cut -d'"' -f4)
[ -n "$BROKERED_USER" ] && [ -n "$BROKERED_PASS" ] || fail "authorize-session returned no brokered vault credentials"
echo "    boundary brokered vault credential: $BROKERED_USER"

echo "==> [end-to-end] brokered credentials actually work against postgres"
"$RUNTIME" exec -e PGPASSWORD="$BROKERED_PASS" postgres-app \
  psql -h 127.0.0.1 -U "$BROKERED_USER" -d appdb -tAc "SELECT count(*) FROM customers" \
  | grep -qE '^[0-9]+$' || fail "brokered credentials rejected by postgres"
echo "    login OK, SELECT on customers OK"

echo
echo "PASS: full chain verified — Consul mesh (mTLS + intentions), Vault dynamic DB creds, Boundary brokered access."
echo
echo "Boundary login:  $LOGIN_NAME / $PASSWORD"
echo "Auth method id:  $AUTH_METHOD_ID"
echo "Target id:       $TARGET_ID"
