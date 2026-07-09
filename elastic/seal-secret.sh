#!/bin/bash
set -euo pipefail

NAMESPACE=elastic
SECRET_NAME=elastic-secrets
SEALED_DIR="$(dirname "${BASH_SOURCE[0]}")/kubernetes/sealed"

mkdir -p "$SEALED_DIR"

kubectl create secret generic "$SECRET_NAME" \
  --namespace "$NAMESPACE" \
  --dry-run=client \
  --from-env-file=.env \
  -o yaml > /tmp/unsealed.yaml

kubeseal --cert kubeseal-pub.pem < /tmp/unsealed.yaml > "$SEALED_DIR/$SECRET_NAME.yaml"
rm /tmp/unsealed.yaml

echo "Sealed secret saved to $SEALED_DIR/$SECRET_NAME.yaml"