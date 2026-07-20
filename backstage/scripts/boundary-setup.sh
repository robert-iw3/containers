#!/bin/sh
# One-shot: wire Boundary as the portal's front door — Vault credential
# store/library, hosts, and two targets: the dev portal itself (what an end
# user on the internet connects to) and the catalog database with brokered
# short-lived Vault credentials (the DBA path).
# Idempotent via /portal-state/boundary-ids.env marker.
set -eu

export BOUNDARY_ADDR=${BOUNDARY_ADDR:-http://boundary:9200}
STATE=/portal-state
IDS="$STATE/boundary-ids.env"

if [ -s "$IDS" ]; then
  echo "boundary-setup: already configured ($(cat "$IDS" | tr '\n' ' '))"
  exit 0
fi

echo "==> waiting for Boundary ops /health"
for i in $(seq 1 90); do
  wget -q -O- --ca-certificate=/portal-certs/ca.crt https://boundary:9203/health >/dev/null 2>&1 && break
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
  name=$1; shift
  boundary "$@" -recovery-config "$RECOVERY" -format table 2>/dev/null \
    | awk -v n="$name" '$1=="ID:"{id=$2} $1=="Name:" && $2==n {print id; exit}'
}

echo "==> scopes"
ORG=$(bcli scopes create -scope-id global -name portal-org -description "Dev portal" 2>/dev/null | jget || true)
[ -n "$ORG" ] || ORG=$(find_by_name portal-org scopes list -scope-id global)
[ -n "$ORG" ] || { echo "FAIL: could not create or find portal-org"; exit 1; }

PROJ=$(bcli scopes create -scope-id "$ORG" -name portal-project 2>/dev/null | jget || true)
[ -n "$PROJ" ] || PROJ=$(find_by_name portal-project scopes list -scope-id "$ORG")
[ -n "$PROJ" ] || { echo "FAIL: could not create or find portal-project"; exit 1; }

echo "==> Vault credential store"
CS=$(bcli credential-stores create vault -scope-id "$PROJ" -name vault-store \
  -vault-address https://vault:8200 \
  -vault-token "$(cat "$STATE/boundary-vault-token")" \
  -vault-ca-cert file:///certs/vault-ca.crt.pem 2>/dev/null | jget || true)
[ -n "$CS" ] || CS=$(find_by_name vault-store credential-stores list -scope-id "$PROJ")
[ -n "$CS" ] || { echo "FAIL: could not create or find vault-store"; exit 1; }

echo "==> credential library: database/creds/dba-readonly"
CL=$(bcli credential-libraries create vault-generic -credential-store-id "$CS" \
  -name dba-readonly -vault-path database/creds/dba-readonly \
  -credential-type username_password 2>/dev/null | jget || true)
[ -n "$CL" ] || CL=$(find_by_name dba-readonly credential-libraries list -credential-store-id "$CS")
[ -n "$CL" ] || { echo "FAIL: could not create or find credential library"; exit 1; }

echo "==> host catalog / hosts / host sets"
HC=$(bcli host-catalogs create static -scope-id "$PROJ" -name portal-hosts 2>/dev/null | jget || true)
[ -n "$HC" ] || HC=$(find_by_name portal-hosts host-catalogs list -scope-id "$PROJ")

H_WEB=$(bcli hosts create static -host-catalog-id "$HC" -name portal-proxy -address portal-proxy 2>/dev/null | jget || true)
[ -n "$H_WEB" ] || H_WEB=$(find_by_name portal-proxy hosts list -host-catalog-id "$HC")
HS_WEB=$(bcli host-sets create static -host-catalog-id "$HC" -name portal-web 2>/dev/null | jget || true)
[ -n "$HS_WEB" ] || HS_WEB=$(find_by_name portal-web host-sets list -host-catalog-id "$HC")
bcli host-sets add-hosts -id "$HS_WEB" -host "$H_WEB" >/dev/null 2>&1 || true

H_DB=$(bcli hosts create static -host-catalog-id "$HC" -name postgres -address postgres 2>/dev/null | jget || true)
[ -n "$H_DB" ] || H_DB=$(find_by_name postgres hosts list -host-catalog-id "$HC")
HS_DB=$(bcli host-sets create static -host-catalog-id "$HC" -name portal-db 2>/dev/null | jget || true)
[ -n "$HS_DB" ] || HS_DB=$(find_by_name portal-db host-sets list -host-catalog-id "$HC")
bcli host-sets add-hosts -id "$HS_DB" -host "$H_DB" >/dev/null 2>&1 || true

echo "==> target: the dev portal (end-user entry point)"
T_WEB=$(bcli targets create tcp -scope-id "$PROJ" -name dev-portal \
  -description "Backstage dev portal (via path-routing proxy) over a brokered session" \
  -default-port 8443 -session-connection-limit -1 2>/dev/null | jget || true)
[ -n "$T_WEB" ] || T_WEB=$(find_by_name dev-portal targets list -scope-id "$PROJ")
[ -n "$T_WEB" ] || { echo "FAIL: could not create or find dev-portal target"; exit 1; }
bcli targets add-host-sources -id "$T_WEB" -host-source "$HS_WEB" >/dev/null 2>&1 || true

echo "==> target: catalog database with brokered Vault credentials"
T_DB=$(bcli targets create tcp -scope-id "$PROJ" -name portal-postgres-dba \
  -description "Catalog Postgres via Vault-brokered dynamic credentials" \
  -default-port 5432 -session-connection-limit -1 2>/dev/null | jget || true)
[ -n "$T_DB" ] || T_DB=$(find_by_name portal-postgres-dba targets list -scope-id "$PROJ")
[ -n "$T_DB" ] || { echo "FAIL: could not create or find portal-postgres-dba target"; exit 1; }
bcli targets add-host-sources -id "$T_DB" -host-source "$HS_DB" >/dev/null 2>&1 || true
bcli targets add-credential-sources -id "$T_DB" -brokered-credential-source "$CL" >/dev/null 2>&1 || true

cat > "$IDS" <<EOF
ORG_ID=$ORG
PROJECT_ID=$PROJ
CREDENTIAL_STORE_ID=$CS
CREDENTIAL_LIBRARY_ID=$CL
PORTAL_TARGET_ID=$T_WEB
DB_TARGET_ID=$T_DB
EOF
chmod 644 "$IDS"

echo "boundary-setup: DONE"
cat "$IDS"
