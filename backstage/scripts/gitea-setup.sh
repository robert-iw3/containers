#!/usr/bin/env bash
# Host-run one-shot: provision the dev-project storage.
#   1. admin user in Gitea (self-registration stays disabled)
#   2. org "devteam" + seed repo "sample-service" with a catalog-info.yaml
#      the portal discovers over the mesh
#   3. store the Gitea credentials in Vault kv (the portal reads them from
#      there at start — they never land in compose env or the image)
# Idempotent: every step tolerates "already exists".
set -euo pipefail

cd "$(dirname "$0")/.."
RUNTIME="${RUNTIME:-podman}"
GITEA_URL="https://127.0.0.1:23000"
CA=./.portal-ca.crt

# shellcheck disable=SC1091
. ./.env

echo "==> extracting the stack CA for host-side TLS calls"
"$RUNTIME" run --rm --user root -v backstage_portal-certs:/portal-certs:ro localhost/vault:2.0.3 \
  cat /portal-certs/ca.crt > "$CA"

echo "==> waiting for Gitea API"
for i in $(seq 1 60); do
  curl -sf --cacert "$CA" "$GITEA_URL/api/healthz" >/dev/null 2>&1 && break
  [ "$i" = 60 ] && { echo "FAIL: gitea never came up"; exit 1; }
  sleep 2
done

echo "==> admin user (via gitea CLI, registration stays disabled)"
"$RUNTIME" exec backstage-gitea gitea admin user create \
    --admin --username "$GITEA_ADMIN_USER" --password "$GITEA_ADMIN_PASSWORD" \
    --email "$GITEA_ADMIN_USER@portal.internal" --must-change-password=false \
  2>&1 | grep -v "$GITEA_ADMIN_PASSWORD" \
  || echo "    admin user already exists"

api() { # api <method> <path> [json-body]
  local method=$1 path=$2 body=${3:-}
  curl -s --cacert "$CA" -o /tmp/gitea-api-out -w '%{http_code}' -X "$method" \
    -u "$GITEA_ADMIN_USER:$GITEA_ADMIN_PASSWORD" \
    -H 'Content-Type: application/json' \
    ${body:+-d "$body"} "$GITEA_URL/api/v1$path"
}

expect() { # expect <desc> <got> <ok-codes...>
  local desc=$1 got=$2; shift 2
  for ok in "$@"; do [ "$got" = "$ok" ] && { echo "    $desc: $got"; return 0; }; done
  echo "FAIL: $desc returned HTTP $got"; cat /tmp/gitea-api-out; echo; exit 1
}

echo "==> org devteam"
expect "create org" "$(api POST /orgs '{"username":"devteam","visibility":"public"}')" 201 409 422

echo "==> seed repo devteam/sample-service"
expect "create repo" "$(api POST /orgs/devteam/repos '{"name":"sample-service","auto_init":true,"default_branch":"main","private":false}')" 201 409

CATALOG_INFO=$(base64 -w0 <<'EOF'
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: sample-service
  description: Seed dev project stored in Gitea, discovered by the portal over the Consul mesh
  tags:
    - seed
spec:
  type: service
  lifecycle: experimental
  owner: devteam
EOF
)
expect "add catalog-info.yaml" \
  "$(api POST /repos/devteam/sample-service/contents/catalog-info.yaml \
      "{\"content\":\"$CATALOG_INFO\",\"message\":\"Register sample-service in the dev portal\"}")" \
  201 422

# org model: the OIDC sign-in resolver matches portal-dev by email against
# this User entity
ORG_YAML=$(base64 -w0 <<'EOF'
apiVersion: backstage.io/v1alpha1
kind: Group
metadata:
  name: devteam
  description: Development team owning the seeded projects
spec:
  type: team
  children: []
---
apiVersion: backstage.io/v1alpha1
kind: User
metadata:
  name: portal-dev
spec:
  profile:
    displayName: Portal Developer
    email: portal-dev@portal.internal
  memberOf: [devteam]
EOF
)
expect "add org.yaml" \
  "$(api POST /repos/devteam/sample-service/contents/org.yaml \
      "{\"content\":\"$ORG_YAML\",\"message\":\"Seed portal org model\"}")" \
  201 422

echo "==> storing Gitea credentials in Vault kv (secret/gitea/portal)"
ROOT_TOKEN=$("$RUNTIME" run --rm --user root -v backstage_portal-state:/portal-state:ro localhost/vault:2.0.3 \
  python3 -c "import json;print(json.load(open('/portal-state/vault-init.json'))['root_token'])")
"$RUNTIME" exec -e VAULT_TOKEN="$ROOT_TOKEN" \
  -e GU="$GITEA_ADMIN_USER" -e GP="$GITEA_ADMIN_PASSWORD" backstage-vault \
  sh -c 'vault kv put secret/gitea/portal username="$GU" password="$GP"' >/dev/null
echo "    stored"

echo "gitea-setup: DONE"
