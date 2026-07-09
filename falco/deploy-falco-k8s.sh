#!/bin/bash

# Script to deploy Falco, Traefik, TinyAuth, Sidekick, WebUI, and Redis to Kubernetes
# Usage: ./deploy-falco-k8s.sh [path_to_yaml]
# Default YAML file: falco-k8s.yaml

set -e

# Generate random 32-char secret for TinyAuth
TINYAUTH_SECRET=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
# Placeholder for htpasswd users (replace with actual values)
# Edit these variables!
TINYAUTH_USERS="tinyauth:\$2y\$10\$..." # Replace with htpasswd -nb tinyauth "password" | sed -e 's/\$/\$\$/g'
TRAEFIK_DASHBOARD_USERS="admin:\$2y\$10\$..." # Replace with htpasswd -nb admin "password" | sed -e 's/\$/\$\$/g'

YAML_FILE=${1:-"falco-k8s.yaml"}
NAMESPACE="falco"
CONFIG_DIR="./config"
DYNAMIC_DIR="./dynamic"
SECRETS_DIR="./secrets/certs"

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
    "$CONFIG_DIR/http_output.yml"
    "$DYNAMIC_DIR/tls.yaml"
)
SECRET_FILES=(
    "$SECRETS_DIR/falco.pem"
    "$SECRETS_DIR/sslcert_chain.pem"
    "$SECRETS_DIR/sslcert_rsa.key.pem"
    "$SECRETS_DIR/sslcert.pem"
)
for file in "${CONFIG_FILES[@]}" "${SECRET_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        error "Required file $file not found"
    fi
done

log "Creating namespace $NAMESPACE if it doesn't exist..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - || error "Failed to create namespace $NAMESPACE"

log "Creating ConfigMap falco-config..."
kubectl create configmap falco-config \
    --from-file=http_output.yml="$CONFIG_DIR/http_output.yml" \
    --from-file=tls.yaml="$DYNAMIC_DIR/tls.yaml" \
    --namespace="$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f - || error "Failed to create ConfigMap"

log "Creating Secret falco-secrets..."
kubectl create secret generic falco-secrets \
    --from-file=falco.pem="$SECRETS_DIR/falco.pem" \
    --from-file=sidekick.ca="$SECRETS_DIR/sslcert_chain.pem" \
    --from-file=sidekick.key="$SECRETS_DIR/sslcert_rsa.key.pem" \
    --from-file=sidekick.cert="$SECRETS_DIR/sslcert.pem" \
    --from-literal=tinyauth.secret="$TINYAUTH_SECRET" \
    --from-literal=tinyauth.users="$TINYAUTH_USERS" \
    --from-literal=traefik.dashboard.users="$TRAEFIK_DASHBOARD_USERS" \
    --namespace="$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f - || error "Failed to create Secret"

log "Applying Kubernetes deployment from $YAML_FILE..."
kubectl apply -f "$YAML_FILE" || error "Failed to apply $YAML_FILE"

log "Waiting for certs Job to complete..."
kubectl wait --for=condition=Complete job/certs --namespace="$NAMESPACE" --timeout=300s || error "Certs Job failed to complete"

log "Waiting for Traefik pod to be ready..."
kubectl wait --for=condition=Ready pod -l app=traefik --namespace="$NAMESPACE" --timeout=300s || error "Traefik pod failed to become ready"

log "Waiting for TinyAuth pod to be ready..."
kubectl wait --for=condition=Ready pod -l app=tinyauth --namespace="$NAMESPACE" --timeout=300s || error "TinyAuth pod failed to become ready"

log "Waiting for Falco pod to be ready..."
kubectl wait --for=condition=Ready pod -l app=falco --namespace="$NAMESPACE" --timeout=300s || error "Falco pod failed to become ready"

log "Waiting for Sidekick pod to be ready..."
kubectl wait --for=condition=Ready pod -l app=sidekick --namespace="$NAMESPACE" --timeout=300s || error "Sidekick pod failed to become ready"

log "Waiting for WebUI pod to be ready..."
kubectl wait --for=condition=Ready pod -l app=webui --namespace="$NAMESPACE" --timeout=300s || error "WebUI pod failed to become ready"

log "Waiting for Redis pod to be ready..."
kubectl wait --for=condition=Ready pod -l app=redis --namespace="$NAMESPACE" --timeout=300s || error "Redis pod failed to become ready"

log "Verifying services..."
kubectl get svc -n "$NAMESPACE"

log "Deployment successful!"
log "To access Traefik dashboard, run:"
log "  kubectl port-forward svc/traefik 8080:8080 -n $NAMESPACE"
log "Then access at: https://dashboard.podman.localhost:8080"
log "To access TinyAuth, run:"
log "  kubectl port-forward svc/tinyauth 3000:3000 -n $NAMESPACE"
log "Then access at: https://tinyauth.local:3000"
log "To access Falco WebUI, run:"
log "  kubectl port-forward svc/webui 2802:2802 -n $NAMESPACE"
log "Then access at: https://falco-webui:2802"
log "To check Falco logs, run:"
log "  kubectl logs -n $NAMESPACE -l app=falco"