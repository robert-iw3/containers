#!/bin/bash

# Script to deploy Elasticsearch, Kibana, Fleet Server, and OTel Collector to Kubernetes
# Usage: ./deploy-elastic-k8s.sh [path_to_yaml] [path_to_env]
# Default YAML file: elastic-k8s.yaml
# Default .env file: .env

set -e

YAML_FILE=${1:-"elastic-k8s.yaml"}
ENV_FILE=${2:-".env"}
NAMESPACE="elastic"
CONFIG_DIR="."
ELASTICSEARCH_CONFIG_DIR="./elasticsearch/config"
KIBANA_CONFIG_DIR="./kibana/config"
SETUP_DIR="./setup"

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

if [ ! -f "$ENV_FILE" ]; then
    error ".env file $ENV_FILE not found"
fi

CONFIG_FILES=(
    "$ELASTICSEARCH_CONFIG_DIR/elasticsearch.yml"
    "$KIBANA_CONFIG_DIR/kibana.yml"
    "$SETUP_DIR/entrypoint.sh"
    "$SETUP_DIR/lib.sh"
    "$SETUP_DIR/roles" # Adjust if roles is a directory
)
for file in "${CONFIG_FILES[@]}"; do
    if [ ! -f "$file" ] && [ ! -d "$file" ]; then
        error "Required file $file not found"
    fi
done

set -a
source "$ENV_FILE"
set +a

REQUIRED_VARS=(
    ELASTIC_VERSION
    ELASTIC_PASSWORD
    KIBANA_SYSTEM_PASSWORD
    LOGSTASH_INTERNAL_PASSWORD
    METRICBEAT_INTERNAL_PASSWORD
    FILEBEAT_INTERNAL_PASSWORD
    HEARTBEAT_INTERNAL_PASSWORD
    MONITORING_INTERNAL_PASSWORD
    BEATS_SYSTEM_PASSWORD
)
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        error "Environment variable $var is not set in $ENV_FILE"
    fi
done

log "Creating namespace $NAMESPACE if it doesn't exist..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - || error "Failed to create namespace $NAMESPACE"

log "Creating ConfigMap elastic-config..."
kubectl create configmap elastic-config \
    --from-file=elasticsearch.yml="$ELASTICSEARCH_CONFIG_DIR/elasticsearch.yml" \
    --from-file=kibana.yml="$KIBANA_CONFIG_DIR/kibana.yml" \
    --from-file=entrypoint.sh="$SETUP_DIR/entrypoint.sh" \
    --from-file=lib.sh="$SETUP_DIR/lib.sh" \
    --from-file=roles="$SETUP_DIR/roles" \
    --namespace="$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f - || error "Failed to create ConfigMap elastic-config"

log "Creating ConfigMap otel-collector-config..."
kubectl create configmap otel-collector-config \
    --from-literal=config.yaml="$(cat <<EOF
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
connectors:
  elasticapm:
processors:
  elastictrace:
exporters:
  elasticsearch:
    endpoints: ["https://elasticsearch-0.elasticsearch-cluster.elastic.svc.cluster.local:9200"]
    user: elastic
    password: "\${ELASTIC_PASSWORD}"
    tls:
      ca_file: /certs/ca/ca.crt
    mapping:
      mode: otel
    logs_dynamic_index:
      enabled: true
    metrics_dynamic_index:
      enabled: true
    traces_dynamic_index:
      enabled: true
    flush:
      interval: 1s
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [elastictrace]
      exporters: [elasticapm, elasticsearch]
    metrics:
      receivers: [otlp]
      processors: []
      exporters: [elasticsearch]
    metrics/aggregated:
      receivers: [elasticapm]
      processors: []
      exporters: [elasticsearch]
    logs:
      receivers: [otlp]
      processors: []
      exporters: [elasticapm, elasticsearch]
EOF
)" \
    --namespace="$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f - || error "Failed to create ConfigMap otel-collector-config"

log "Creating Secret elastic-secrets..."
kubectl create secret generic elastic-secrets \
    --from-literal=ELASTIC_PASSWORD="$ELASTIC_PASSWORD" \
    --from-literal=KIBANA_SYSTEM_PASSWORD="$KIBANA_SYSTEM_PASSWORD" \
    --from-literal=LOGSTASH_INTERNAL_PASSWORD="$LOGSTASH_INTERNAL_PASSWORD" \
    --from-literal=METRICBEAT_INTERNAL_PASSWORD="$METRICBEAT_INTERNAL_PASSWORD" \
    --from-literal=FILEBEAT_INTERNAL_PASSWORD="$FILEBEAT_INTERNAL_PASSWORD" \
    --from-literal=HEARTBEAT_INTERNAL_PASSWORD="$HEARTBEAT_INTERNAL_PASSWORD" \
    --from-literal=MONITORING_INTERNAL_PASSWORD="$MONITORING_INTERNAL_PASSWORD" \
    --from-literal=BEATS_SYSTEM_PASSWORD="$BEATS_SYSTEM_PASSWORD" \
    --namespace="$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f - || error "Failed to create Secret"

log "Applying Kubernetes deployment from $YAML_FILE..."
sed "s/\${ELASTIC_VERSION}/$ELASTIC_VERSION/g" "$YAML_FILE" | kubectl apply -f - || error "Failed to apply $YAML_FILE"

log "Waiting for Elasticsearch pods to be ready..."
kubectl wait --for=condition=Ready pod -l app=elasticsearch --namespace="$NAMESPACE" --timeout=300s || error "Elasticsearch pods failed to become ready"

log "Waiting for Kibana pod to be ready..."
kubectl wait --for=condition=Ready pod -l app=kibana --namespace="$NAMESPACE" --timeout=300s || error "Kibana pod failed to become ready"

log "Waiting for Fleet Server pod to be ready..."
kubectl wait --for=condition=Ready pod -l app=fleet-server --namespace="$NAMESPACE" --timeout=300s || error "Fleet Server pod failed to become ready"

log "Waiting for OTel Collector pod to be ready..."
kubectl wait --for=condition=Ready pod -l app=otel-collector --namespace="$NAMESPACE" --timeout=300s || error "OTel Collector pod failed to become ready"

log "Verifying services..."
kubectl get svc -n "$NAMESPACE"

log "Deployment successful!"
log "To access Kibana, run:"
log "  kubectl port-forward svc/kibana 5601:5601 -n $NAMESPACE"
log "Then access at: https://localhost:5601"
log "To access Fleet Server, run:"
log "  kubectl port-forward svc/fleet-server 8220:8220 -n $NAMESPACE"
log "To access OTel Collector (gRPC), run:"
log "  kubectl port-forward svc/otel-collector 4317:4317 -n $NAMESPACE"
log "To access OTel Collector (HTTP), run:"
log "  kubectl port-forward svc/otel-collector 4318:4318 -n $NAMESPACE"
log "To check Elasticsearch cluster health, run:"
log "  kubectl exec -it elasticsearch-0 -n $NAMESPACE -- curl -k --cacert /usr/share/elasticsearch/config/certs/ca/ca.crt https://localhost:9200/_cluster/health"
log "To verify OTel Collector connectivity, send a test telemetry signal to http://otel-collector.elastic.svc.cluster.local:4318 or grpc://otel-collector.elastic.svc.cluster.local:4317"