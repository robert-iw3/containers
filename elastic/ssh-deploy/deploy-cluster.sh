#!/usr/bin/env bash
# Deploy a multi-host Elastic cluster over plain SSH (no Ansible). Generates the CA +
# per-node certs once, then for each host in cluster.hosts: preps it, pushes the certs
# + node-up.sh, starts the container, and finally sets the kibana_system password.
#
#   ELASTIC_PASSWORD=... KIBANA_SYSTEM_PASSWORD=... ./deploy-cluster.sh [cluster.hosts]
#
# Requires: podman/docker locally (to mint certs), ssh/scp to each host, and
# podman/docker on each host.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
HOSTS="${1:-$DIR/cluster.hosts}"
VERSION="${ELASTIC_VERSION:-9.4.3}"
CLUSTER="${CLUSTER_NAME:-elastic-cluster}"
HEAP="${ES_HEAP:-2g}"
ELASTIC_PW="${ELASTIC_PASSWORD:?set ELASTIC_PASSWORD}"
KIBANA_PW="${KIBANA_SYSTEM_PASSWORD:?set KIBANA_SYSTEM_PASSWORD}"
RT="$(command -v podman >/dev/null 2>&1 && echo podman || echo docker)"
WORK="$(mktemp -d)"; CERTS="$WORK/certs"; mkdir -p "$CERTS"

# 1. parse inventory -> node names + roles + targets + advertise IPs
declare -a NODES ROLES TARGETS IPS
es_i=0; kb_i=0
while read -r role target ip _; do
  [[ -z "${role:-}" || "$role" == \#* ]] && continue
  if [ "$role" = es ]; then es_i=$((es_i + 1)); name=$(printf "es%02d" "$es_i")
  else kb_i=$((kb_i + 1)); name=$(printf "kibana%02d" "$kb_i"); fi
  NODES+=("$name"); ROLES+=("$role"); TARGETS+=("$target"); IPS+=("$ip")
done < "$HOSTS"

ES_IPS=(); ES_NAMES=()
for i in "${!NODES[@]}"; do
  [ "${ROLES[$i]}" = es ] && { ES_IPS+=("${IPS[$i]}"); ES_NAMES+=("${NODES[$i]}"); }
done
SEEDS=$(IFS=,; echo "${ES_IPS[*]}")
INIT_MASTERS=$(IFS=,; echo "${ES_NAMES[*]}")
ES_HOSTS="[$(printf '"https://%s:9200",' "${ES_IPS[@]}" | sed 's/,$//')]"

# 2. mint CA + per-node certs (SAN = node name + its advertise IP)
instances=""
for i in "${!NODES[@]}"; do
  instances+="  - name: ${NODES[$i]}\\n    dns: [${NODES[$i]}, localhost]\\n    ip: [${IPS[$i]}, 127.0.0.1]\\n"
done
echo "== generating CA + certs for: ${NODES[*]} =="
"$RT" run --rm -v "$CERTS:/certs:Z" "docker.elastic.co/elasticsearch/elasticsearch:${VERSION}" bash -c "
  set -e
  bin/elasticsearch-certutil ca --silent --pem -out /certs/ca.zip; unzip -o /certs/ca.zip -d /certs
  printf 'instances:\\n${instances}' > /certs/instances.yml
  bin/elasticsearch-certutil cert --silent --pem -out /certs/certs.zip --in /certs/instances.yml --ca-cert /certs/ca/ca.crt --ca-key /certs/ca/ca.key
  unzip -o /certs/certs.zip -d /certs
  for n in ${NODES[*]}; do cat /certs/\$n/\$n.crt /certs/ca/ca.crt > /certs/\$n/\$n.chain.pem; done
"

# 3. deploy each node over SSH
for i in "${!NODES[@]}"; do
  t="${TARGETS[$i]}"
  echo "== deploying ${NODES[$i]} (${ROLES[$i]}) on ${t} =="
  ssh "$t" 'sudo mkdir -p /opt/elastic/certs && sudo chown -R "$(id -u):$(id -g)" /opt/elastic'
  scp -rq "$CERTS/." "$t:/opt/elastic/certs/"
  scp -q "$DIR/node-up.sh" "$DIR/../host-prep/prepare-host.sh" "$t:/opt/elastic/"
  cat > "$WORK/node.env" <<EOF
ROLE=${ROLES[$i]}
NODE=${NODES[$i]}
CLUSTER=$CLUSTER
VERSION=$VERSION
ADVERTISE=${IPS[$i]}
SEEDS=$SEEDS
INIT_MASTERS=$INIT_MASTERS
ES_HOSTS=$ES_HOSTS
ELASTIC_PW=$ELASTIC_PW
KIBANA_PW=$KIBANA_PW
HEAP=$HEAP
EOF
  scp -q "$WORK/node.env" "$t:/opt/elastic/node.env"
  ssh "$t" 'chmod +x /opt/elastic/node-up.sh /opt/elastic/prepare-host.sh && bash /opt/elastic/node-up.sh'
done

# 4. set kibana_system password on the first ES node
first="${ES_IPS[0]}"
echo "== waiting for https://${first}:9200 then setting kibana_system password =="
until curl -s --cacert "$CERTS/ca/ca.crt" "https://${first}:9200" | grep -q "missing authentication"; do sleep 5; done
curl -s -X POST --cacert "$CERTS/ca/ca.crt" -u "elastic:${ELASTIC_PW}" \
  -H "Content-Type: application/json" \
  "https://${first}:9200/_security/user/kibana_system/_password" \
  -d "{\"password\":\"${KIBANA_PW}\"}" >/dev/null
echo "== cluster deployed. CA/certs kept in ${CERTS} (remove when no longer needed). =="
