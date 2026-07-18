#!/usr/bin/env bash
# One-shot: initialize/unseal Vault, wire the database secrets engine to
# postgres-app, and mint scoped tokens for Boundary and demo-api.
# Idempotent: safe to re-run; state lives in /demo-state.
set -euo pipefail

export VAULT_ADDR=${VAULT_ADDR:-https://vault:8200}
export VAULT_CACERT=${VAULT_CACERT:-/certs/vault-ca.crt.pem}
STATE=/demo-state

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

echo "==> waiting for postgres-app"
for i in $(seq 1 60); do
  (exec 3<>/dev/tcp/postgres-app/5432) 2>/dev/null && { exec 3<&- 3>&-; break; }
  [ "$i" = 60 ] && { echo "FAIL: postgres-app never came up"; exit 1; }
  sleep 2
done

echo "==> configuring database secrets engine"
vault secrets enable database 2>/dev/null || echo "    database engine already enabled"

vault write database/config/appdb \
  plugin_name=postgresql-database-plugin \
  allowed_roles=app-readonly \
  connection_url="postgresql://{{username}}:{{password}}@postgres-app:5432/appdb?sslmode=disable" \
  username="app_admin" \
  password="$APP_DB_PASSWORD"

vault write database/roles/app-readonly \
  db_name=appdb \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl=10m \
  max_ttl=1h

echo "==> policies"
vault policy write boundary-creds - <<'EOF'
path "database/creds/app-readonly" {
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

vault policy write app-creds - <<'EOF'
path "database/creds/app-readonly" {
  capabilities = ["read"]
}
EOF

echo "==> tokens for Boundary (orphan, periodic) and demo-api"
# minted once: Boundary stores its copy in the credential store, so a new
# token here would silently diverge from what Boundary uses
if [ ! -s "$STATE/boundary-vault-token" ]; then
  vault token create -orphan -period=24h -policy=boundary-creds -format=json \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['auth']['client_token'])" \
    > "$STATE/boundary-vault-token"
  chmod 600 "$STATE/boundary-vault-token"
fi

if [ ! -s "$STATE/app-token" ]; then
  vault token create -orphan -period=24h -policy=app-creds -format=json \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['auth']['client_token'])" \
    > "$STATE/app-token"
  chmod 644 "$STATE/app-token"
fi

echo "==> smoke: mint one credential"
vault read database/creds/app-readonly -format=json \
  | python3 -c "import json,sys;print('    issued db user:', json.load(sys.stdin)['data']['username'])"

echo "vault-setup: DONE"
