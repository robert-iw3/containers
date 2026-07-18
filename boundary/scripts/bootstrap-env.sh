#!/usr/bin/env bash
# Generate a .env with random postgres password and AEAD KMS keys.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -s .env ]; then
  echo ".env already exists — leaving it alone"
  exit 0
fi

cat > .env <<EOF
POSTGRES_USER=boundary
POSTGRES_PASSWORD=$(openssl rand -hex 24)
POSTGRES_DB=boundary
BOUNDARY_ROOT_KEY=$(openssl rand -base64 32)
BOUNDARY_WORKER_AUTH_KEY=$(openssl rand -base64 32)
BOUNDARY_RECOVERY_KEY=$(openssl rand -base64 32)
BOUNDARY_PUBLIC_HOST=127.0.0.1
EOF
chmod 600 .env
echo "wrote boundary/.env (chmod 600)"
