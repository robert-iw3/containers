#!/usr/bin/env bash
# Generate a .env with random admin and read-only API keys.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -s .env ]; then
  echo ".env already exists — leaving it alone"
  exit 0
fi

cat > .env <<EOF
WEAVIATE_ADMIN_KEY=$(openssl rand -hex 24)
WEAVIATE_READONLY_KEY=$(openssl rand -hex 24)
EOF
chmod 600 .env
echo "wrote weaviate/.env (chmod 600)"
