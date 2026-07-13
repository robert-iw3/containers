#!/usr/bin/env bash
# Runs ON a target host (pushed there by deploy-cluster.sh over SSH). Starts one
# Elastic node -- Elasticsearch or Kibana -- as a container wired into the cluster,
# using the certs and node.env the orchestrator scp'd to /opt/elastic.
set -euo pipefail

. /opt/elastic/node.env          # ROLE NODE CLUSTER VERSION ADVERTISE SEEDS INIT_MASTERS ES_HOSTS ELASTIC_PW KIBANA_PW HEAP
CERTS=/opt/elastic/certs
RT="$(command -v podman >/dev/null 2>&1 && echo podman || echo docker)"

# Balance security with performance before starting the JVM (needs root; best-effort).
[ -x /opt/elastic/prepare-host.sh ] && sudo /opt/elastic/prepare-host.sh >/dev/null 2>&1 || true

if [ "$ROLE" = es ]; then
  "$RT" pull "docker.elastic.co/elasticsearch/elasticsearch:${VERSION}"
  "$RT" rm -f "elastic-${NODE}" >/dev/null 2>&1 || true
  "$RT" run -d --name "elastic-${NODE}" --hostname "$NODE" --network host \
    --restart unless-stopped --ulimit memlock=-1:-1 \
    -v "${CERTS}:/usr/share/elasticsearch/config/certs:ro" \
    -v "elastic-${NODE}-data:/usr/share/elasticsearch/data" \
    -e "node.name=${NODE}" -e "cluster.name=${CLUSTER}" \
    -e "discovery.seed_hosts=${SEEDS}" \
    -e "cluster.initial_master_nodes=${INIT_MASTERS}" \
    -e "network.publish_host=${ADVERTISE}" \
    -e "ELASTIC_PASSWORD=${ELASTIC_PW}" \
    -e "ES_JAVA_OPTS=-Xms${HEAP} -Xmx${HEAP}" \
    -e "bootstrap.memory_lock=true" \
    -e "xpack.security.enabled=true" \
    -e "xpack.license.self_generated.type=trial" \
    -e "xpack.security.authc.api_key.enabled=true" \
    -e "xpack.security.http.ssl.enabled=true" \
    -e "xpack.security.http.ssl.key=certs/${NODE}/${NODE}.key" \
    -e "xpack.security.http.ssl.certificate=certs/${NODE}/${NODE}.chain.pem" \
    -e "xpack.security.http.ssl.certificate_authorities=certs/ca/ca.crt" \
    -e "xpack.security.transport.ssl.enabled=true" \
    -e "xpack.security.transport.ssl.key=certs/${NODE}/${NODE}.key" \
    -e "xpack.security.transport.ssl.certificate=certs/${NODE}/${NODE}.crt" \
    -e "xpack.security.transport.ssl.certificate_authorities=certs/ca/ca.crt" \
    -e "xpack.security.transport.ssl.verification_mode=certificate" \
    "docker.elastic.co/elasticsearch/elasticsearch:${VERSION}"
  echo "started elasticsearch node ${NODE} (advertise ${ADVERTISE})"

elif [ "$ROLE" = kibana ]; then
  "$RT" pull "docker.elastic.co/kibana/kibana:${VERSION}"
  "$RT" rm -f "${NODE}" >/dev/null 2>&1 || true
  "$RT" run -d --name "${NODE}" --network host --restart unless-stopped \
    -v "${CERTS}:/usr/share/kibana/config/certs:ro" \
    -v "${NODE}-data:/usr/share/kibana/data" \
    -e "SERVER_NAME=${NODE}" \
    -e "ELASTICSEARCH_HOSTS=${ES_HOSTS}" \
    -e "ELASTICSEARCH_USERNAME=kibana_system" \
    -e "ELASTICSEARCH_PASSWORD=${KIBANA_PW}" \
    -e "ELASTICSEARCH_SSL_CERTIFICATEAUTHORITIES=config/certs/ca/ca.crt" \
    -e "SERVER_SSL_ENABLED=true" \
    -e "SERVER_SSL_CERTIFICATE=config/certs/${NODE}/${NODE}.crt" \
    -e "SERVER_SSL_KEY=config/certs/${NODE}/${NODE}.key" \
    "docker.elastic.co/kibana/kibana:${VERSION}"
  echo "started kibana ${NODE}"
else
  echo "unknown role: ${ROLE}"; exit 1
fi
