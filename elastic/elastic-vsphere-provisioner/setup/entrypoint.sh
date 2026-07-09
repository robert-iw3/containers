#!/bin/bash
set -e

# === CONFIG ===
# IPs / hostnames are injected by the orchestrator (Ansible env vars)
ES_IPS="${ES_IPS:-}"
ES_HOSTS="${ES_HOSTS:-}"
KIBANA_IP="${KIBANA_IP:-}"
KIBANA_HOST="${KIBANA_HOST:-}"
FLEET_IP="${FLEET_IP:-}"
FLEET_HOST="${FLEET_HOST:-}"

# Fallbacks (should never be used if orchestrator works)
: "${ES_IPS:=192.168.1.11,192.168.1.12,192.168.1.13}"
: "${ES_HOSTS:=es-node1,es-node2,es-node3}"
: "${KIBANA_IP:=192.168.1.14}"
: "${KIBANA_HOST:=kibana-vm}"
: "${FLEET_IP:=$KIBANA_IP}"
: "${FLEET_HOST:=$KIBANA_HOST}"

CERTS_DIR="/usr/share/elasticsearch/config/certs"

# === VALIDATE ===
[[ -z "$ELASTIC_PASSWORD" ]] && { echo "ERROR: ELASTIC_PASSWORD not set"; exit 1; }
[[ -z "$KIBANA_SYSTEM_PASSWORD" ]] && { echo "ERROR: KIBANA_SYSTEM_PASSWORD not set"; exit 1; }

# === GENERATE CERTS WITH REAL IPs & HOSTNAMES ===
if [[ ! -f "$CERTS_DIR/ca.zip" ]]; then
    echo "Generating CA..."
    bin/elasticsearch-certutil ca --silent --pem -out "$CERTS_DIR/ca.zip"
    unzip -o "$CERTS_DIR/ca.zip" -d "$CERTS_DIR"
fi

if [[ ! -f "$CERTS_DIR/certs.zip" ]]; then
    echo "Generating certificates with real IPs & hostnames..."

    # Build instances.yml dynamically
    {
        echo "instances:"
        IFS=',' read -ra ES_IP_ARR <<< "$ES_IPS"
        IFS=',' read -ra ES_HOST_ARR <<< "$ES_HOSTS"

        # ES nodes
        for i in "${!ES_HOST_ARR[@]}"; do
            host="${ES_HOST_ARR[i]}"
            ip="${ES_IP_ARR[i]}"
            cat <<EOF
  - name: $host
    dns: [$host, ${host}.local]
    ip: [$ip]
EOF
        done

        # Kibana
        cat <<EOF
  - name: $KIBANA_HOST
    dns: [$KIBANA_HOST, ${KIBANA_HOST}.local]
    ip: [$KIBANA_IP]
EOF

        # Fleet (may share Kibana host)
        if [[ "$FLEET_HOST" != "$KIBANA_HOST" ]]; then
            cat <<EOF
  - name: $FLEET_HOST
    dns: [$FLEET_HOST, ${FLEET_HOST}.local]
    ip: [$FLEET_IP]
EOF
        fi
    } > "$CERTS_DIR/instances.yml"

    bin/elasticsearch-certutil cert --silent --pem \
        --in "$CERTS_DIR/instances.yml" \
        --out "$CERTS_DIR/certs.zip" \
        --ca-cert "$CERTS_DIR/ca/ca.crt" \
        --ca-key "$CERTS_DIR/ca/ca.key"

    unzip -o "$CERTS_DIR/certs.zip" -d "$CERTS_DIR"

    # Build chain.pem for every node
    for node in "${ES_HOST_ARR[@]}" "$KIBANA_HOST" ${FLEET_HOST:+$FLEET_HOST}; do
        if [[ -f "$CERTS_DIR/$node/$node.crt" ]]; then
            cat "$CERTS_DIR/$node/$node.crt" "$CERTS_DIR/ca/ca.crt" > "$CERTS_DIR/$node/$node.chain.pem"
        fi
    done
fi

# === PERMISSIONS ===
chown -R root:root "$CERTS_DIR"
find "$CERTS_DIR" -type d -exec chmod 750 {} \;
find "$CERTS_DIR" -type f -exec chmod 640 {} \;

# === WAIT FOR ES ===
echo "Waiting for Elasticsearch cluster..."
until curl -s --cacert "$CERTS_DIR/ca/ca.crt" "https://${ES_HOST_ARR[0]}:9200/_cluster/health" | grep -q "cluster_name"; do
    sleep 10
done

# === SET KIBANA PASSWORD ===
echo "Setting kibana_system password..."
until curl -s -X POST --cacert "$CERTS_DIR/ca/ca.crt" \
    -u "elastic:${ELASTIC_PASSWORD}" \
    -H "Content-Type: application/json" \
    "https://${ES_HOST_ARR[0]}:9200/_security/user/kibana_system/_password" \
    -d "{\"password\":\"${KIBANA_SYSTEM_PASSWORD}\"}" | grep -q "{}"; do
    sleep 10
done

echo "Setup complete! Certs generated with real IPs & hostnames:"
echo " ES IPs   : $ES_IPS"
echo " ES Hosts : $ES_HOSTS"
echo " Kibana   : $KIBANA_IP ($KIBANA_HOST)"
echo " Fleet    : $FLEET_IP ($FLEET_HOST)"