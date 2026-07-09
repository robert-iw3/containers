#!/bin/bash

# Script to deploy OpenSearch and OpenSearch Dashboards to Kubernetes
# Usage: ./deploy-opensearch-k8s.sh [path_to_yaml]
# Default YAML file: opensearch-k8s.yaml

# Exit on error
set -e

# Default values
YAML_FILE=${1:-"opensearch-k8s.yaml"}
NAMESPACE="opensearch"
CONFIG_DIR="."
CERTS_DIR="./certs"
SECURITY_DIR="./security"
CREDS_FILE="./.creds.curlrc"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
    exit 1
}

if ! command -v kubectl &> /dev/null; then
    error "kubectl is not installed or not found in PATH"
fi

if [ ! -f "$YAML_FILE" ]; then
    error "Kubernetes YAML file $YAML_FILE not found"
fi

CONFIG_FILES=(
    "$CONFIG_DIR/opensearch.yml"
    "$SECURITY_DIR/audit.yml"
    "$SECURITY_DIR/action_groups.yml"
    "$SECURITY_DIR/config.yml"
    "$SECURITY_DIR/internal_users.yml"
    "$SECURITY_DIR/roles.yml"
    "$SECURITY_DIR/roles_mapping.yml"
    "$SECURITY_DIR/tenants.yml"
    "$CONFIG_DIR/opensearch_dashboards.yml"
)
CERT_FILES=(
    "$CERTS_DIR/ca-trust"
    "$CERTS_DIR/admin-key.pem"
    "$CERTS_DIR/admin.pem"
    "$CERTS_DIR/node1-key.pem"
    "$CERTS_DIR/node1.pem"
    "$CERTS_DIR/node2-key.pem"
    "$CERTS_DIR/node2.pem"
    "$CERTS_DIR/node3-key.pem"
    "$CERTS_DIR/node3.pem"
    "$CERTS_DIR/node4-key.pem"
    "$CERTS_DIR/node4.pem"
    "$CERTS_DIR/root-ca.pem"
    "$CERTS_DIR/client-key.pem"
    "$CERTS_DIR/client.pem"
    "$CREDS_FILE"
)

for file in "${CONFIG_FILES[@]}" "${CERT_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        error "Required file $file not found"
    fi
done

log "Creating namespace $NAMESPACE if it doesn't exist..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - || error "Failed to create namespace $NAMESPACE"

log "Creating ConfigMap opensearch-config..."
kubectl create configmap opensearch-config \
    --from-file=opensearch.yml="$CONFIG_DIR/opensearch.yml" \
    --from-file=audit.yml="$SECURITY_DIR/audit.yml" \
    --from-file=action_groups.yml="$SECURITY_DIR/action_groups.yml" \
    --from-file=config.yml="$SECURITY_DIR/config.yml" \
    --from-file=internal_users.yml="$SECURITY_DIR/internal_users.yml" \
    --from-file=roles.yml="$SECURITY_DIR/roles.yml" \
    --from-file=roles_mapping.yml="$SECURITY_DIR/roles_mapping.yml" \
    --from-file=tenants.yml="$SECURITY_DIR/tenants.yml" \
    --from-file=opensearch_dashboards.yml="$CONFIG_DIR/opensearch_dashboards.yml" \
    --namespace="$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f - || error "Failed to create ConfigMap"

log "Creating Secret opensearch-secrets..."
kubectl create secret generic opensearch-secrets \
    --from-file=ca-trust="$CERTS_DIR/ca-trust" \
    --from-file=admin-key.pem="$CERTS_DIR/admin-key.pem" \
    --from-file=admin.pem="$CERTS_DIR/admin.pem" \
    --from-file=node1-key.pem="$CERTS_DIR/node1-key.pem" \
    --from-file=node1.pem="$CERTS_DIR/node1.pem" \
    --from-file=node2-key.pem="$CERTS_DIR/node2-key.pem" \
    --from-file=node2.pem="$CERTS_DIR/node2.pem" \
    --from-file=node3-key.pem="$CERTS_DIR/node3-key.pem" \
    --from-file=node3.pem="$CERTS_DIR/node3.pem" \
    --from-file=node4-key.pem="$CERTS_DIR/node4-key.pem" \
    --from-file=node4.pem="$CERTS_DIR/node4.pem" \
    --from-file=root-ca.pem="$CERTS_DIR/root-ca.pem" \
    --from-file=client-key.pem="$CERTS_DIR/client-key.pem" \
    --from-file=client.pem="$CERTS_DIR/client.pem" \
    --from-file=.creds.curlrc="$CREDS_FILE" \
    --namespace="$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f - || error "Failed to create Secret"

log "Applying Kubernetes deployment from $YAML_FILE..."
kubectl apply -f "$YAML_FILE" || error "Failed to apply $YAML_FILE"

log "Waiting for OpenSearch pods to be ready..."
kubectl wait --for=condition=Ready pod -l app=opensearch --namespace="$NAMESPACE" --timeout=300s || error "OpenSearch pods failed to become ready"

log "Waiting for OpenSearch Dashboards pod to be ready..."
kubectl wait --for=condition=Ready pod -l app=opensearch-dashboards --namespace="$NAMESPACE" --timeout=300s || error "OpenSearch Dashboards pod failed to become ready"

log "Verifying services..."
kubectl get svc -n "$NAMESPACE"

log "Deployment successful!"
log "To access OpenSearch Dashboards, run:"
log "  kubectl port-forward svc/opensearch-dashboards 5601:5601 -n $NAMESPACE"
log "Then access at: https://localhost:5601"
log "To check cluster health, run:"
log "  kubectl exec -it opensearch-0 -n $NAMESPACE -- curl -k https://localhost:9200/_cluster/health"