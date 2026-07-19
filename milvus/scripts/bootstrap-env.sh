#!/usr/bin/env bash
# Generate a .env with random MinIO and Milvus root credentials.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -s .env ]; then
  echo ".env already exists — leaving it alone"
  exit 0
fi

cat > .env <<EOF
MINIO_ROOT_USER=milvus-storage
MINIO_ROOT_PASSWORD=$(openssl rand -hex 24)
MILVUS_ROOT_PASSWORD=$(openssl rand -hex 24)
EOF
chmod 600 .env
echo "wrote milvus/.env (chmod 600)"
