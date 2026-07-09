#!/bin/bash
set -e

# === CONFIG FROM ORCHESTRATOR (via .env + Ansible) ===
# Format: HOSTNAMES="es-master1,es-master2,es-data-hot1,es-data-hot2"
#         IPS="192.168.1.11,192.168.1.12,192.168.1.13,192.168.1.14"
ES_HOSTNAMES="${ES_HOSTNAMES}"
ES_IPS="${ES_IPS}"
KIBANA_HOSTNAMES="${KIBANA_HOSTNAMES}"
KIBANA_IPS="${KIBANA_IPS}"
FLEET_HOSTNAMES="${FLEET_HOSTNAMES}"
FLEET_IPS="${FLEET_IPS}"

CERTS_DIR="/usr/share/elasticsearch/config/certs"

# === VALIDATE ===
if [ -z "$ELASTIC_PASSWORD" ]; then
  echo "ERROR: ELASTIC_PASSWORD not set"
  exit 1
fi
if [ -z "$KIBANA_SYSTEM_PASSWORD" ]; then
  echo "ERROR: KIBANA_SYSTEM_PASSWORD not set"
  exit 1
fi
if [ -z "$ES_HOSTNAMES" ] || [ -z "$ES_IPS" ]; then
  echo "ERROR: ES_HOSTNAMES or ES_IPS not set"
  exit 1
fi

# === GENERATE CERTS WITH DYNAMIC HOSTNAMES/IPs ===
if [ ! -f "$CERTS_DIR/ca.zip" ]; then
  echo "Generating CA..."
  bin/elasticsearch-certutil ca --silent --pem -out "$CERTS_DIR/ca.zip"
  unzip -o "$CERTS_DIR/ca.zip" -d "$CERTS_DIR"
fi

if [ ! -f "$CERTS_DIR/certs.zip" ]; then
  echo "Generating certificates with real hostnames and IPs..."

  # Convert comma-separated strings to arrays
  IFS=',' read -ra ES_HOST_ARRAY <<< "$ES_HOSTNAMES"
  IFS=',' read -ra ES_IP_ARRAY <<< "$ES_IPS"
  IFS=',' read -ra KIBANA_HOST_ARRAY <<< "$KIBANA_HOSTNAMES"
  IFS=',' read -ra KIBANA_IP_ARRAY <<< "$KIBANA_IPS"
  IFS=',' read -ra FLEET_HOST_ARRAY <<< "$FLEET_HOSTNAMES"
  IFS=',' read -ra FLEET_IP_ARRAY <<< "$FLEET_IPS"

  # Build instances.yml
  cat > "$CERTS_DIR/instances.yml" <<EOF
instances:
EOF

  # Add ES nodes
  for i in "${!ES_HOST_ARRAY[@]}"; do
    host="${ES_HOST_ARRAY[$i]}"
    ip="${ES_IP_ARRAY[$i]}"
    cat >> "$CERTS_DIR/instances.yml" <<EOF
  - name: $host
    dns: [$host, ${host}.local]
    ip: [$ip]
EOF
  done

  # Add Kibana
  for i in "${!KIBANA_HOST_ARRAY[@]}"; do
    host="${KIBANA_HOST_ARRAY[$i]}"
    ip="${KIBANA_IP_ARRAY[$i]}"
    cat >> "$CERTS_DIR/instances.yml" <<EOF
  - name: $host
    dns: [$host, ${host}.local]
    ip: [$ip]
EOF
  done

  # Add Fleet
  for i in "${!FLEET_HOST_ARRAY[@]}"; do
    host="${FLEET_HOST_ARRAY[$i]}"
    ip="${FLEET_IP_ARRAY[$i]}"
    cat >> "$CERTS_DIR/instances.yml" <<EOF
  - name: $host
    dns: [$host, ${host}.local]
    ip: [$ip]
EOF
  done

  # Generate certs
  bin/elasticsearch-certutil cert --silent --pem \
    --in "$CERTS_DIR/instances.yml" \
    --out "$CERTS_DIR/certs.zip" \
    --ca-cert "$CERTS_DIR/ca/ca.crt" \
    --ca-key "$CERTS_DIR/ca/ca.key"

  unzip -o "$CERTS_DIR/certs.zip" -d "$CERTS_DIR"

  # Create chain.pem for each node
  for node in "${ES_HOST_ARRAY[@]}" "${KIBANA_HOST_ARRAY[@]}" "${FLEET_HOST_ARRAY[@]}"; do
    if [ -f "$CERTS_DIR/$node/$node.crt" ]; then
      cat "$CERTS_DIR/$node/$node.crt" "$CERTS_DIR/ca/ca.crt" > "$CERTS_DIR/$node/$node.chain.pem"
    fi
  done
fi

# === PERMISSIONS ===
chown -R root:root "$CERTS_DIR"
find "$CERTS_DIR" -type d -exec chmod 750 {} \;
find "$CERTS_DIR" -type f -exec chmod 640 {} \;

# === WAIT FOR FIRST ES NODE ===
FIRST_ES_HOST="${ES_HOST_ARRAY[0]}"
echo "Waiting for Elasticsearch at $FIRST_ES_HOST..."
until curl -s --cacert "$CERTS_DIR/ca/ca.crt" "https://$FIRST_ES_HOST:9200/_cluster/health" | grep -q "cluster_name"; do
  sleep 10
done

# === SET KIBANA PASSWORD ===
echo "Setting kibana_system password..."
until curl -s -X POST --cacert "$CERTS_DIR/ca/ca.crt" \
  -u "elastic:${ELASTIC_PASSWORD}" \
  -H "Content-Type: application/json" \
  "https://$FIRST_ES_HOST:9200/_security/user/kibana_system/_password" \
  -d "{\"password\":\"${KIBANA_SYSTEM_PASSWORD}\"}" | grep -q "{}"; do
  sleep 10
done

echo "Setup complete!"
echo "Certs generated for:"
echo "  ES: $ES_HOSTNAMES"
echo "  Kibana: $KIBANA_HOSTNAMES"
echo "  Fleet: $FLEET_HOSTNAMES"