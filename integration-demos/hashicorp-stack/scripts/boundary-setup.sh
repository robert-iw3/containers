#!/usr/bin/env bash
# One-shot: wire Boundary to Vault — credential store (Vault token),
# credential library (database/creds/app-readonly), host + target for
# postgres-app with brokered credentials.
# Idempotent via /demo-state/boundary-ids.env marker.
set -euo pipefail

export BOUNDARY_ADDR=${BOUNDARY_ADDR:-http://boundary:9200}
STATE=/demo-state
IDS="$STATE/boundary-ids.env"

if [ -s "$IDS" ]; then
  echo "boundary-setup: already configured ($(cat "$IDS" | tr '\n' ' '))"
  exit 0
fi

echo "==> waiting for Boundary ops /health"
for i in $(seq 1 90); do
  wget -q -O- http://boundary:9203/health >/dev/null 2>&1 && break
  [ "$i" = 90 ] && { echo "FAIL: boundary /health never responded"; exit 1; }
  sleep 2
done

echo "==> waiting for Vault token from vault-setup"
for i in $(seq 1 90); do
  [ -s "$STATE/boundary-vault-token" ] && break
  [ "$i" = 90 ] && { echo "FAIL: no boundary vault token appeared"; exit 1; }
  sleep 2
done

# recovery KMS auth: no admin password needed for provisioning
RECOVERY=/home/boundary/recovery.hcl
cat > "$RECOVERY" <<EOF
kms "aead" {
  purpose   = "recovery"
  aead_type = "aes-gcm"
  key       = "${BOUNDARY_RECOVERY_KEY}"
  key_id    = "global_recovery"
}
EOF

bcli() { boundary "$@" -recovery-config "$RECOVERY" -format json; }
# no python/jq in the boundary image; the item's own id is the first "id" key
# in the compact JSON output
jget() { grep -o '"id": *"[^"]*"' | head -1 | cut -d'"' -f4; }

# find an existing resource id by name from table-format list output
# (names are unique per parent, so create-or-lookup makes reruns safe)
find_by_name() {
  local name=$1; shift
  boundary "$@" -recovery-config "$RECOVERY" -format table 2>/dev/null \
    | awk -v n="$name" '$1=="ID:"{id=$2} $1=="Name:" && $2==n {print id; exit}'
}

echo "==> scopes"
ORG=$(bcli scopes create -scope-id global -name demo-org -description "HashiCorp stack demo" 2>/dev/null | jget || true)
[ -n "$ORG" ] || ORG=$(find_by_name demo-org scopes list -scope-id global)
[ -n "$ORG" ] || { echo "FAIL: could not create or find demo-org"; exit 1; }

PROJ=$(bcli scopes create -scope-id "$ORG" -name demo-project 2>/dev/null | jget || true)
[ -n "$PROJ" ] || PROJ=$(find_by_name demo-project scopes list -scope-id "$ORG")
[ -n "$PROJ" ] || { echo "FAIL: could not create or find demo-project"; exit 1; }

echo "==> Vault credential store"
CS=$(bcli credential-stores create vault -scope-id "$PROJ" -name vault-store \
  -vault-address https://vault:8200 \
  -vault-token "$(cat "$STATE/boundary-vault-token")" \
  -vault-ca-cert file:///certs/vault-ca.crt.pem 2>/dev/null | jget || true)
[ -n "$CS" ] || CS=$(find_by_name vault-store credential-stores list -scope-id "$PROJ")
[ -n "$CS" ] || { echo "FAIL: could not create or find vault-store"; exit 1; }

echo "==> credential library: database/creds/app-readonly"
CL=$(bcli credential-libraries create vault-generic -credential-store-id "$CS" \
  -name app-readonly -vault-path database/creds/app-readonly \
  -credential-type username_password 2>/dev/null | jget || true)
[ -n "$CL" ] || CL=$(find_by_name app-readonly credential-libraries list -credential-store-id "$CS")
[ -n "$CL" ] || { echo "FAIL: could not create or find credential library"; exit 1; }

echo "==> host catalog / host / host set for postgres-app"
HC=$(bcli host-catalogs create static -scope-id "$PROJ" -name demo-hosts 2>/dev/null | jget || true)
[ -n "$HC" ] || HC=$(find_by_name demo-hosts host-catalogs list -scope-id "$PROJ")
H=$(bcli hosts create static -host-catalog-id "$HC" -name postgres-app -address postgres-app 2>/dev/null | jget || true)
[ -n "$H" ] || H=$(find_by_name postgres-app hosts list -host-catalog-id "$HC")
HS=$(bcli host-sets create static -host-catalog-id "$HC" -name postgres-hosts 2>/dev/null | jget || true)
[ -n "$HS" ] || HS=$(find_by_name postgres-hosts host-sets list -host-catalog-id "$HC")
bcli host-sets add-hosts -id "$HS" -host "$H" >/dev/null 2>&1 || true

echo "==> target with brokered Vault credentials"
T=$(bcli targets create tcp -scope-id "$PROJ" -name postgres-appdb \
  -description "PostgreSQL via Vault-brokered dynamic credentials" \
  -default-port 5432 -session-connection-limit -1 2>/dev/null | jget || true)
[ -n "$T" ] || T=$(find_by_name postgres-appdb targets list -scope-id "$PROJ")
[ -n "$T" ] || { echo "FAIL: could not create or find target"; exit 1; }
bcli targets add-host-sources -id "$T" -host-source "$HS" >/dev/null 2>&1 || true
bcli targets add-credential-sources -id "$T" -brokered-credential-source "$CL" >/dev/null 2>&1 || true

cat > "$IDS" <<EOF
ORG_ID=$ORG
PROJECT_ID=$PROJ
CREDENTIAL_STORE_ID=$CS
CREDENTIAL_LIBRARY_ID=$CL
TARGET_ID=$T
EOF
chmod 644 "$IDS"

echo "boundary-setup: DONE"
cat "$IDS"
