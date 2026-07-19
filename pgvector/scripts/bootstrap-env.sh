#!/usr/bin/env bash
# Generate a .env with random postgres and application-role passwords.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -s .env ]; then
  echo ".env already exists — leaving it alone"
  exit 0
fi

cat > .env <<EOF
POSTGRES_USER=vectoradmin
POSTGRES_PASSWORD=$(openssl rand -hex 24)
POSTGRES_DB=vectors
APP_RW_PASSWORD=$(openssl rand -hex 24)
APP_RO_PASSWORD=$(openssl rand -hex 24)
EOF
chmod 600 .env
echo "wrote pgvector/.env (chmod 600)"
