#!/usr/bin/env bash
# One-shot: initialize/unseal Vault, wire the database secrets engine to the
# portal's Postgres (static role for the portal, dynamic role for DBAs),
# enable kv-v2 for the Gitea credentials, and mint scoped tokens for the
# portal and for Boundary.
# Idempotent: safe to re-run; state lives in /portal-state.
set -euo pipefail

export VAULT_ADDR=${VAULT_ADDR:-https://vault:8200}
export VAULT_CACERT=${VAULT_CACERT:-/certs/vault-ca.crt.pem}
STATE=/portal-state

echo "==> waiting for Vault API"
for i in $(seq 1 60); do
  curl -sf --cacert "$VAULT_CACERT" \
    "$VAULT_ADDR/v1/sys/health?uninitcode=200&sealedcode=200" >/dev/null 2>&1 && break
  [ "$i" = 60 ] && { echo "FAIL: vault API never came up"; exit 1; }
  sleep 2
done

# NOTE: `vault status` exits non-zero when sealed/uninitialized, so capture
# output first — piping it directly trips pipefail and corrupts the value
init_status() {
  local out
  out=$(vault status -format=json 2>/dev/null || true)
  echo "$out" | python3 -c "import json,sys;print(str(json.load(sys.stdin)['$1']).lower())" 2>/dev/null || echo unknown
}

if [ "$(init_status initialized)" != "true" ]; then
  echo "==> initializing (1 share / threshold 1 — demo only)"
  vault operator init -key-shares=1 -key-threshold=1 -format=json > "$STATE/vault-init.json"
  chmod 600 "$STATE/vault-init.json"
fi

UNSEAL=$(python3 -c "import json;print(json.load(open('$STATE/vault-init.json'))['unseal_keys_b64'][0])")
export VAULT_TOKEN=$(python3 -c "import json;print(json.load(open('$STATE/vault-init.json'))['root_token'])")

if [ "$(init_status sealed)" = "true" ]; then
  echo "==> unsealing"
  vault operator unseal "$UNSEAL" >/dev/null
fi

echo "==> waiting for postgres"
for i in $(seq 1 60); do
  (exec 3<>/dev/tcp/postgres/5432) 2>/dev/null && { exec 3<&- 3>&-; break; }
  [ "$i" = 60 ] && { echo "FAIL: postgres never came up"; exit 1; }
  sleep 2
done

echo "==> configuring database secrets engine"
# right after unseal Vault may briefly reject writes; retry until the mount
# is really there instead of trusting the enable call's exit code
for i in $(seq 1 30); do
  vault secrets enable database 2>&1 | grep -v '^$' || true
  vault secrets list -format=json 2>/dev/null | grep -q '"database/"' && break
  [ "$i" = 30 ] && { echo "FAIL: database engine never mounted"; exit 1; }
  sleep 2
done

vault write database/config/portaldb \
  plugin_name=postgresql-database-plugin \
  allowed_roles="backstage-portal,dba-readonly" \
  connection_url="postgresql://{{username}}:{{password}}@postgres:5432/postgres?sslmode=verify-ca&sslrootcert=/portal-certs/ca.crt" \
  username="pgadmin" \
  password="$PG_ADMIN_PASSWORD"

# The portal's own DB identity: fixed username, password owned + rotated by
# Vault (rotates immediately on registration, then every rotation_period).
vault write database/static-roles/backstage-portal \
  db_name=portaldb \
  username=backstage \
  rotation_period=86400 2>/dev/null || echo "    static role already registered"

# Short-lived DBA credentials, brokered to humans by Boundary.
vault write database/roles/dba-readonly \
  db_name=portaldb \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT pg_read_all_data TO \"{{name}}\";" \
  default_ttl=10m \
  max_ttl=1h

echo "==> kv store for Gitea credentials"
for i in $(seq 1 30); do
  vault secrets enable -path=secret kv-v2 2>&1 | grep -v '^$' || true
  vault secrets list -format=json 2>/dev/null | grep -q '"secret/"' && break
  [ "$i" = 30 ] && { echo "FAIL: kv engine never mounted"; exit 1; }
  sleep 2
done

echo "==> policies"
vault policy write portal-creds - <<'EOF'
path "database/static-creds/backstage-portal" {
  capabilities = ["read"]
}
path "secret/data/gitea/portal" {
  capabilities = ["read"]
}
path "secret/data/oidc/portal" {
  capabilities = ["read"]
}
EOF

vault policy write boundary-creds - <<'EOF'
path "database/creds/dba-readonly" {
  capabilities = ["read"]
}
path "sys/leases/renew" {
  capabilities = ["update"]
}
path "sys/leases/revoke" {
  capabilities = ["update"]
}
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
path "auth/token/renew-self" {
  capabilities = ["update"]
}
EOF

echo "==> tokens for the portal and for Boundary (orphan, periodic)"
# minted once: Boundary stores its copy in the credential store, so a new
# token here would silently diverge from what Boundary uses
if [ ! -s "$STATE/boundary-vault-token" ]; then
  vault token create -orphan -period=24h -policy=boundary-creds -format=json \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['auth']['client_token'])" \
    > "$STATE/boundary-vault-token"
  chmod 600 "$STATE/boundary-vault-token"
fi

if [ ! -s "$STATE/backstage-token" ]; then
  vault token create -orphan -period=72h -policy=portal-creds -format=json \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['auth']['client_token'])" \
    > "$STATE/backstage-token"
  chmod 644 "$STATE/backstage-token"
fi

echo "==> smoke: read the portal's rotated static credential"
vault read database/static-creds/backstage-portal -format=json \
  | python3 -c "import json,sys;print('    portal db user:', json.load(sys.stdin)['data']['username'])"

echo "vault-setup: DONE"
