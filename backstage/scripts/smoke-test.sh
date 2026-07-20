#!/usr/bin/env bash
# End-to-end UAT for the dev portal stack:
#   1. Consul: leader, catalog holds postgres/gitea/backstage/vault, mesh
#      intentions allow backstage -> postgres|gitea and deny everything else
#   2. Vault: initialized + unsealed, static portal creds + kv Gitea creds
#   3. Gitea: seed dev project exists and its catalog-info.yaml is served
#   4. Backstage: healthy, catalog API (authed with the static UAT token)
#      contains the Gitea-hosted component — proving mesh DB + mesh SCM reads
#   5. Boundary: admin auth; end-user session to the portal target returns
#      the portal UI; DBA session to postgres brokers working Vault creds
set -euo pipefail

cd "$(dirname "$0")/.."

RUNTIME="${RUNTIME:-podman}"
ADMIN_FILE=".boundary-admin.json"
fail() { echo "FAIL: $*"; exit 1; }

# shellcheck disable=SC1091
. ./.env

echo "==> [consul] waiting for leader"
for i in $(seq 1 60); do
  LEADER=$("$RUNTIME" exec backstage-consul curl -sf --cacert /portal-certs/ca.crt https://127.0.0.1:8501/v1/status/leader 2>/dev/null || true)
  [ -n "$LEADER" ] && [ "$LEADER" != '""' ] && break
  [ "$i" = 60 ] && fail "no consul leader"
  sleep 2
done

echo "==> [vault] waiting for vault-setup to finish"
for i in $(seq 1 120); do
  [ "$("$RUNTIME" logs backstage-vault-setup 2>&1 | grep -c 'vault-setup: DONE')" -gt 0 ] && break
  [ "$("$RUNTIME" logs backstage-vault-setup 2>&1 | grep -c '^FAIL')" -gt 0 ] && { "$RUNTIME" logs backstage-vault-setup | tail -5; fail "vault-setup failed"; }
  [ "$i" = 120 ] && { "$RUNTIME" logs backstage-vault-setup | tail -10; fail "vault-setup never finished"; }
  sleep 2
done
echo "    vault-setup complete"

echo "==> [boundary] waiting for boundary-setup to finish"
for i in $(seq 1 120); do
  [ "$("$RUNTIME" logs backstage-boundary-setup 2>&1 | grep -c 'boundary-setup: DONE\|already configured')" -gt 0 ] && break
  [ "$i" = 120 ] && { "$RUNTIME" logs backstage-boundary-setup | tail -10; fail "boundary-setup never finished"; }
  sleep 2
done
echo "    boundary-setup complete"

echo "==> [consul] catalog services"
SERVICES=$("$RUNTIME" exec backstage-consul curl -sf --cacert /portal-certs/ca.crt https://127.0.0.1:8501/v1/catalog/services)
for svc in vault postgres gitea backstage; do
  echo "$SERVICES" | grep -q "\"$svc\"" || fail "$svc not in consul catalog"
done
echo "    vault, postgres, gitea, backstage registered"

echo "==> [consul] mesh intentions (deny by default)"
icheck() { # icheck <source> <dest> <true|false>
  local out
  out=$("$RUNTIME" exec backstage-consul curl -sf \
    --cacert /portal-certs/ca.crt "https://127.0.0.1:8501/v1/connect/intentions/check?source=$1&destination=$2")
  echo "$out" | grep -q "\"Allowed\": *$3" || fail "intention $1 -> $2 expected Allowed=$3: $out"
}
icheck backstage postgres true
icheck backstage gitea true
icheck gitea postgres false
icheck some-other-svc postgres false
icheck some-other-svc gitea false
echo "    allow backstage->postgres, backstage->gitea; deny everything else: OK"

echo "==> [vault] portal's rotated static credential + kv Gitea secret"
ROOT_TOKEN=$("$RUNTIME" run --rm --user root -v backstage_portal-state:/portal-state:ro localhost/vault:2.0.3 \
  python3 -c "import json;print(json.load(open('/portal-state/vault-init.json'))['root_token'])")
STATIC_USER=$("$RUNTIME" exec -e VAULT_TOKEN="$ROOT_TOKEN" backstage-vault \
  vault read -field=username database/static-creds/backstage-portal)
[ "$STATIC_USER" = "backstage" ] || fail "static role username '$STATIC_USER' != backstage"
"$RUNTIME" exec -e VAULT_TOKEN="$ROOT_TOKEN" backstage-vault \
  vault kv get -field=username secret/gitea/portal >/dev/null || fail "gitea kv secret missing"
echo "    static db credential + gitea kv secret: OK"

echo "==> [gitea] seed dev project"
"$RUNTIME" run --rm --user root -v backstage_portal-certs:/portal-certs:ro localhost/vault:2.0.3 \
  cat /portal-certs/ca.crt > .portal-ca.crt
CATALOG_HTTP=$(curl -s --cacert .portal-ca.crt -o /dev/null -w '%{http_code}' \
  "https://127.0.0.1:23000/devteam/sample-service/raw/branch/main/catalog-info.yaml")
[ "$CATALOG_HTTP" = "200" ] || fail "gitea raw catalog-info.yaml returned HTTP $CATALOG_HTTP"
echo "    devteam/sample-service with catalog-info.yaml: OK"

echo "==> [backstage] waiting for both deployments (Vault secrets + mesh DB + boot)"
for replica in backstage-portal-a backstage-portal-b; do
  for i in $(seq 1 150); do
    "$RUNTIME" exec "$replica" curl -sf http://127.0.0.1:7007/.backstage/health/v1/readiness >/dev/null 2>&1 && break
    [ "$i" = 150 ] && { "$RUNTIME" logs --tail 25 "$replica"; fail "$replica never became ready"; }
    sleep 4
  done
  DB_USER_LINE=$("$RUNTIME" logs "$replica" 2>&1 | grep 'secrets loaded' | tail -1 || true)
  echo "$DB_USER_LINE" | grep -q 'db user: backstage' || fail "$replica did not load Vault-issued db creds: $DB_USER_LINE"
  echo "    $replica ready, booted with Vault-issued db credentials"
done

echo "==> [postgres] per-plugin logical databases (one DBMS, split logical DBs)"
PLUGIN_DBS=$("$RUNTIME" exec backstage-postgres psql -U pgadmin -d postgres -tAc \
  "SELECT datname FROM pg_database WHERE datname LIKE 'backstage_plugin_%' ORDER BY datname")
echo "$PLUGIN_DBS" | sed 's/^/      /'
for db in backstage_plugin_catalog backstage_plugin_auth backstage_plugin_app; do
  echo "$PLUGIN_DBS" | grep -q "^$db$" || fail "expected logical database $db is missing"
done
echo "    per-plugin logical databases present"

echo "==> [proxy] path routing: /api/{catalog,search} -> B, all else -> A"
ROUTE_A=$("$RUNTIME" exec backstage-portal-a curl -s --cacert /portal-certs/ca.crt -D - -o /dev/null https://portal-proxy:8443/ | tr -d '\r')
echo "$ROUTE_A" | grep -qi '^x-portal-deployment: a' || fail "UI traffic not routed to deployment A: $ROUTE_A"
ROUTE_B=$("$RUNTIME" exec backstage-portal-a curl -s --cacert /portal-certs/ca.crt -D - -o /dev/null \
  -H "Authorization: Bearer $UAT_STATIC_TOKEN" https://portal-proxy:8443/api/catalog/entities | tr -d '\r')
echo "$ROUTE_B" | grep -qi '^x-portal-deployment: b' || fail "catalog traffic not routed to deployment B: $ROUTE_B"
echo "    routing verified via X-Portal-Deployment headers"

echo "==> [backstage] catalog API sees the Gitea-hosted component (via proxy + mesh)"
for i in $(seq 1 60); do
  ENTITY=$("$RUNTIME" exec backstage-portal-a curl -sf --cacert /portal-certs/ca.crt \
    -H "Authorization: Bearer $UAT_STATIC_TOKEN" \
    "https://portal-proxy:8443/api/catalog/entities/by-name/component/default/sample-service" 2>/dev/null || true)
  echo "$ENTITY" | grep -q '"sample-service"' && break
  [ "$i" = 60 ] && { "$RUNTIME" logs --tail 25 backstage-portal-b; fail "sample-service never appeared in the catalog"; }
  sleep 5
done
echo "    component sample-service ingested from Gitea over the mesh"

UNAUTHED=$("$RUNTIME" exec backstage-portal-a curl -s --cacert /portal-certs/ca.crt -o /dev/null -w '%{http_code}' \
  "https://portal-proxy:8443/api/catalog/entities" || true)
[ "$UNAUTHED" = "401" ] || fail "catalog API without a token should be 401, got $UNAUTHED"
echo "    catalog API rejects unauthenticated requests (401): OK"

echo "==> [catalog] org model from Gitea (OIDC sign-in resolver targets)"
for kind in user/default/portal-dev group/default/devteam; do
  "$RUNTIME" exec backstage-portal-a curl -sf --cacert /portal-certs/ca.crt \
    -H "Authorization: Bearer $UAT_STATIC_TOKEN" \
    "https://portal-proxy:8443/api/catalog/entities/by-name/$kind" >/dev/null \
    || fail "org entity $kind missing from catalog"
done
echo "    User portal-dev + Group devteam ingested"

echo "==> [keycloak] realm, issuer, and token issuance"
ISSUER=$("$RUNTIME" exec backstage-portal-a curl -sf --cacert /portal-certs/ca.crt \
  "https://keycloak:8443/realms/portal/.well-known/openid-configuration" \
  | grep -o '"issuer":"[^"]*"' | cut -d'"' -f4)
[ "$ISSUER" = "https://127.0.0.1:28443/realms/portal" ] \
  || fail "unexpected OIDC issuer: $ISSUER (browser-facing hostname misconfigured)"
echo "    issuer: $ISSUER"

OIDC_SECRET=$("$RUNTIME" run --rm --user root -v backstage_portal-state:/portal-state:ro localhost/vault:2.0.3 \
  cat /portal-state/oidc-client-secret)
TOKEN_RESP=$("$RUNTIME" exec backstage-portal-a curl -sf --cacert /portal-certs/ca.crt \
  -d "grant_type=password&client_id=backstage-portal&client_secret=$OIDC_SECRET&username=portal-dev&password=$PORTAL_DEV_PASSWORD&scope=openid" \
  "https://keycloak:8443/realms/portal/protocol/openid-connect/token" || true)
echo "$TOKEN_RESP" | grep -q '"access_token"' || fail "keycloak did not issue a token for portal-dev: $TOKEN_RESP"
echo "    keycloak issues tokens for portal-dev: OK"

VAULT_OIDC=$("$RUNTIME" exec -e VAULT_TOKEN="$ROOT_TOKEN" backstage-vault \
  vault kv get -field=client_secret secret/oidc/portal)
[ "$VAULT_OIDC" = "$OIDC_SECRET" ] || fail "vault kv oidc secret diverges from keycloak client secret"
echo "    OIDC client secret held in Vault kv matches: OK"

echo "==> [backstage] OIDC provider wired (auth start redirects to Keycloak)"
AUTH_START=$("$RUNTIME" exec backstage-portal-a curl -s --cacert /portal-certs/ca.crt -o /dev/null \
  -w '%{http_code} %{redirect_url}' \
  "https://portal-proxy:8443/api/auth/oidc/start?env=production" || true)
echo "$AUTH_START" | grep -qE '^30[0-9] https://127\.0\.0\.1:28443/realms/portal' \
  || fail "auth start did not redirect to keycloak: $AUTH_START"
echo "    /api/auth/oidc/start redirects to Keycloak: OK"

echo "==> [boundary] admin auth"
# a stale admin file (e.g. from a previous boundary database) fails auth —
# drop it and re-parse the init credentials from the logs
if [ -s "$ADMIN_FILE" ]; then
  CUR_AMPW=$("$RUNTIME" logs backstage-boundary 2>&1 | grep -oE 'ampw_[A-Za-z0-9]+' | sed -n 1p || true)
  FILE_AMPW=$(grep -o '"auth_method_id":"[^"]*"' "$ADMIN_FILE" | cut -d'"' -f4)
  if [ -n "$CUR_AMPW" ] && [ "$CUR_AMPW" != "$FILE_AMPW" ]; then
    echo "    $ADMIN_FILE is stale (auth method changed) — refreshing from logs"
    rm -f "$ADMIN_FILE"
  fi
fi
if [ ! -s "$ADMIN_FILE" ]; then
  LOGS=$("$RUNTIME" logs backstage-boundary 2>&1)
  AUTH_METHOD_ID=$(echo "$LOGS" | grep -oE 'ampw_[A-Za-z0-9]+' | sed -n 1p || true)
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

TOKEN=$("$RUNTIME" exec -e BOUNDARY_ADDR=https://127.0.0.1:9200 -e BOUNDARY_CACERT=/portal-certs/ca.crt -e BPW="$PASSWORD" backstage-boundary \
  boundary authenticate password -auth-method-id "$AUTH_METHOD_ID" \
  -login-name "$LOGIN_NAME" -password env://BPW -keyring-type=none -format=json 2>/dev/null \
  | grep -o '"token": *"[^"]*"' | sed -n 1p | cut -d'"' -f4 || true)
[ -n "$TOKEN" ] || fail "boundary authentication failed"
echo "    admin authenticated"

IDS=$("$RUNTIME" run --rm --user root -v backstage_portal-state:/portal-state:ro localhost/vault:2.0.3 \
  cat /portal-state/boundary-ids.env)
PORTAL_TARGET_ID=$(echo "$IDS" | grep PORTAL_TARGET_ID | cut -d= -f2)
DB_TARGET_ID=$(echo "$IDS" | grep DB_TARGET_ID | cut -d= -f2)
[ -n "$PORTAL_TARGET_ID" ] && [ -n "$DB_TARGET_ID" ] || fail "boundary-setup recorded no target ids"

echo "==> [end-user] brokered session to the portal serves the UI + catalog API"
PORTAL_BODY=$("$RUNTIME" exec -e BOUNDARY_ADDR=https://127.0.0.1:9200 -e BOUNDARY_CACERT=/portal-certs/ca.crt -e BT="$TOKEN" \
  -e UAT="$UAT_STATIC_TOKEN" backstage-boundary sh -c '
  boundary connect -target-id '"$PORTAL_TARGET_ID"' -token env://BT \
    -listen-addr 127.0.0.1 -listen-port 27007 >/dev/null 2>&1 &
  CPID=$!
  sleep 4
  wget -q -O- --ca-certificate=/portal-certs/ca.crt https://127.0.0.1:27007/ 2>/dev/null
  rc=$?
  echo "---API---"
  wget -q -O- --ca-certificate=/portal-certs/ca.crt --header "Authorization: Bearer $UAT" \
    "https://127.0.0.1:27007/api/catalog/entities/by-name/component/default/sample-service" 2>/dev/null
  rc2=$?
  kill $CPID 2>/dev/null
  [ $rc -eq 0 ] && [ $rc2 -eq 0 ]') || fail "could not fetch portal through a boundary session"
echo "$PORTAL_BODY" | grep -qi 'backstage\|<html' || fail "boundary session response does not look like the portal UI"
echo "$PORTAL_BODY" | grep -q '"sample-service"' || fail "catalog API through boundary session did not return the seed component"
echo "    portal UI + catalog API served through Boundary session: OK"

echo "==> [dba] brokered Vault credentials for postgres actually work"
SESSION=$("$RUNTIME" exec -e BOUNDARY_ADDR=https://127.0.0.1:9200 -e BOUNDARY_CACERT=/portal-certs/ca.crt -e BT="$TOKEN" backstage-boundary \
  boundary targets authorize-session -id "$DB_TARGET_ID" -token env://BT -format=json)
BROKERED_USER=$(echo "$SESSION" | grep -o '"username": *"v-[^"]*"' | sed -n 1p | cut -d'"' -f4 || true)
BROKERED_PASS=$(echo "$SESSION" | grep -o '"password": *"[^"]*"' | sed -n 1p | cut -d'"' -f4 || true)
[ -n "$BROKERED_USER" ] && [ -n "$BROKERED_PASS" ] || fail "authorize-session returned no brokered vault credentials"
echo "    brokered vault credential: $BROKERED_USER"

"$RUNTIME" exec -e PGPASSWORD="$BROKERED_PASS" backstage-postgres \
  psql -h 127.0.0.1 -U "$BROKERED_USER" -d backstage_plugin_catalog \
  -tAc "SELECT count(*) FROM final_entities" \
  | grep -qE '^[0-9]+$' || fail "brokered credentials rejected by postgres"
echo "    DBA login OK, read on portal catalog data OK"

echo
echo "PASS: full chain verified — Boundary-only ingress, Vault-managed secrets,"
echo "      Consul mesh with deny-by-default intentions, Gitea-backed catalog."
echo
echo "Boundary login:    $LOGIN_NAME / $PASSWORD"
echo "Auth method id:    $AUTH_METHOD_ID"
echo "Portal target id:  $PORTAL_TARGET_ID"
echo "DB target id:      $DB_TARGET_ID"
