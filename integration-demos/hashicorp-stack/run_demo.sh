#!/usr/bin/env bash
# One-command bring-up of the full HashiCorp stack demo.
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE="${COMPOSE:-podman-compose}"

if [ ! -s .env ]; then
  echo "==> generating .env with random secrets"
  cat > .env <<EOF
APP_DB_PASSWORD=$(openssl rand -hex 24)
BOUNDARY_DB_PASSWORD=$(openssl rand -hex 24)
BOUNDARY_ROOT_KEY=$(openssl rand -base64 32)
BOUNDARY_WORKER_AUTH_KEY=$(openssl rand -base64 32)
BOUNDARY_RECOVERY_KEY=$(openssl rand -base64 32)
BOUNDARY_PUBLIC_ADDR=127.0.0.1:19202
EOF
  chmod 600 .env
fi

echo "==> building and starting the stack"
$COMPOSE up -d --build

echo "==> running smoke test (waits for setup jobs to finish)"
./scripts/smoke-test.sh

cat <<'EOF'

Demo is up. Entry points:
  Consul UI    http://localhost:18500/ui        (catalog, mesh, intentions)
  Vault UI     https://localhost:18200/ui       (token: see 'podman exec demo-vault-setup' output or /demo-state/vault-init.json)
  Boundary UI  http://localhost:19200           (admin creds: printed by smoke test)
  demo-api     http://localhost:18080           (fresh Vault DB creds + mesh on every request)

Full session broker flow from your workstation (needs psql):
  boundary authenticate password -addr http://localhost:19200 \
      -auth-method-id <ampw_...> -login-name admin
  boundary connect postgres -addr http://localhost:19200 \
      -target-id <ttcp_...> -dbname appdb
(the smoke test prints both IDs; Boundary injects a Vault-issued user/password
 that expires in 10 minutes)
EOF
