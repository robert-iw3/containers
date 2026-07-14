#!/usr/bin/env bash
# Deploy a multi-host OpenSearch cluster over SSH without ansible. Mints certs,
# prepares each host, ships certs + config, and starts a node container per host
# over TLS. Reads cluster.hosts (node-name ssh-target advertise-host).
#
#   OPENSEARCH_INITIAL_ADMIN_PASSWORD=... ./deploy-cluster.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
VERSION="${OPENSEARCH_VERSION:-3.2.0}"
: "${OPENSEARCH_INITIAL_ADMIN_PASSWORD:?set OPENSEARCH_INITIAL_ADMIN_PASSWORD}"

mapfile -t HOSTS < <(grep -vE '^\s*#|^\s*$' "${HERE}/cluster.hosts")
SEED_HOSTS=""
for line in "${HOSTS[@]}"; do
  SEED_HOSTS="${SEED_HOSTS}$(echo "$line" | awk '{print $3}'),"
done
SEED_HOSTS="${SEED_HOSTS%,}"

echo "==> Generating certs for ${#HOSTS[@]} nodes"
( cd "${ROOT}/certs" && bash generate-certificates.sh -n "${#HOSTS[@]}" )

i=0
for line in "${HOSTS[@]}"; do
  i=$((i + 1))
  NODE=$(echo "$line" | awk '{print $1}')
  TARGET=$(echo "$line" | awk '{print $2}')
  ADV=$(echo "$line" | awk '{print $3}')
  echo "==> [${NODE}] preparing ${TARGET}"
  ssh "${TARGET}" 'sudo mkdir -p /opt/opensearch/certs /opt/opensearch/security /opt/opensearch/config'
  scp "${ROOT}/certs/root-ca.pem" "${ROOT}/certs/admin.pem" "${ROOT}/certs/admin-key.pem" \
      "${ROOT}/certs/node${i}.pem" "${ROOT}/certs/node${i}-key.pem" "${TARGET}:/tmp/oscerts/" 2>/dev/null || \
    { ssh "${TARGET}" 'mkdir -p /tmp/oscerts'; scp "${ROOT}/certs/root-ca.pem" "${ROOT}/certs/admin.pem" \
      "${ROOT}/certs/admin-key.pem" "${ROOT}/certs/node${i}.pem" "${ROOT}/certs/node${i}-key.pem" "${TARGET}:/tmp/oscerts/"; }
  scp -r "${ROOT}/security" "${ROOT}/opensearch.yml" "${TARGET}:/tmp/osconf/" 2>/dev/null || \
    { ssh "${TARGET}" 'mkdir -p /tmp/osconf'; scp -r "${ROOT}/security" "${ROOT}/opensearch.yml" "${TARGET}:/tmp/osconf/"; }
  scp "${ROOT}/host-prep/prepare-host.sh" "${TARGET}:/tmp/prepare-host.sh"

  echo "==> [${NODE}] starting node on ${ADV}"
  ssh "${TARGET}" \
    NODE="${NODE}" ADV="${ADV}" SEED="${SEED_HOSTS}" VERSION="${VERSION}" \
    PW="${OPENSEARCH_INITIAL_ADMIN_PASSWORD}" IDX="${i}" 'bash -s' <<'REMOTE'
set -e
sudo bash /tmp/prepare-host.sh
sudo install -d /opt/opensearch/certs /opt/opensearch/config/opensearch-security
sudo cp /tmp/oscerts/root-ca.pem /opt/opensearch/certs/
sudo cp /tmp/oscerts/admin.pem /opt/opensearch/certs/
sudo cp /tmp/oscerts/admin-key.pem /opt/opensearch/certs/
sudo cp /tmp/oscerts/node${IDX}.pem /opt/opensearch/certs/node.pem
sudo cp /tmp/oscerts/node${IDX}-key.pem /opt/opensearch/certs/node-key.pem
sudo cp /tmp/osconf/opensearch.yml /opt/opensearch/config/opensearch.yml
sudo cp /tmp/osconf/security/*.yml /opt/opensearch/config/opensearch-security/
CENGINE=$(command -v podman || command -v docker)
sudo "$CENGINE" rm -f opensearch 2>/dev/null || true
sudo "$CENGINE" run -d --name opensearch --network host --restart unless-stopped \
  --ulimit memlock=-1:-1 --ulimit nofile=65536:65536 \
  -e cluster.name=opensearch-cluster -e node.name="${NODE}" \
  -e discovery.seed_hosts="${SEED}" -e cluster.initial_cluster_manager_nodes="${SEED}" \
  -e bootstrap.memory_lock=true -e DISABLE_INSTALL_DEMO_CONFIG=true \
  -e OPENSEARCH_INITIAL_ADMIN_PASSWORD="${PW}" \
  -e network.publish_host="${ADV}" \
  -v /opt/opensearch/certs:/usr/share/opensearch/config/certs:ro \
  -v /opt/opensearch/config/opensearch.yml:/usr/share/opensearch/config/opensearch.yml:ro \
  -v /opt/opensearch/config/opensearch-security:/usr/share/opensearch/config/opensearch-security:ro \
  "opensearchproject/opensearch:${VERSION}"
REMOTE
done

echo "==> Cluster nodes started. Initialize the security index from any node with securityadmin.sh."
