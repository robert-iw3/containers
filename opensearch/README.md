# OpenSearch (production)

A security-enabled, TLS OpenSearch 3.2.0 cluster + Dashboards, deployable to a
single host, multiple hosts, or Kubernetes. Topology is config-driven.

## Layout

| Path | Purpose |
| --- | --- |
| `gen_opensearch.py` + `stack.config.yml` | Render a compose for any topology |
| `docker-compose.yml` | Committed 4-node reference stack |
| `opensearch.yml`, `security/` | Node config + security plugin config |
| `certs/generate-certificates.sh` | Mint the CA, node, admin, client certs |
| `host-prep/` | Host tuning (max_map_count, memlock, swappiness, THP) |
| `ssh-deploy/`, `ansible/` | Multi-host deploy (with or without ansible) |
| `opensearch-k8s.yaml` + `deploy-opensearch-k8s.sh` | Kubernetes (StatefulSet + PDB + Dashboards HPA) |
| `siem/` | ISM lifecycle policies + labeled data-stream templates |
| `data-prepper/` | Universal ingestion add-on (http + otel -> labeled indices) |
| `curator/`, `setup/` | Index maintenance, security bootstrap |

## Quick start (single host)

```bash
cp .env.example .env               # set OPENSEARCH_INITIAL_ADMIN_PASSWORD
( cd certs && ./generate-certificates.sh )
sudo bash host-prep/prepare-host.sh
docker compose up -d --build
```

Dashboards: https://localhost:5601 — OpenSearch: https://localhost:9200

## Any topology

Edit `stack.config.yml` (node count, cluster managers, dashboards, heap `auto`,
tls/security), then:

```bash
python3 gen_opensearch.py stack.config.yml > docker-compose.generated.yml
docker compose -f docker-compose.generated.yml up -d --build
```

Heap auto-sizes to 50% of host RAM split across nodes (capped 31g); memory limits
track 2x heap.

## Multi-host & Kubernetes

- **Ansible**: `ansible-playbook -i ansible/inventory.ini ansible/deploy-opensearch.yml`
- **SSH (no ansible)**: fill `ssh-deploy/cluster.hosts`, then
  `OPENSEARCH_INITIAL_ADMIN_PASSWORD=... ssh-deploy/deploy-cluster.sh`
- **Kubernetes**: `./deploy-opensearch-k8s.sh` (creates ConfigMap/Secret from the
  local config and certs, applies `opensearch-k8s.yaml`).

## SIEM labeled indices

Route datasets to `logs-<dataset>-<namespace>` data streams with an ISM
hot -> warm -> delete lifecycle:

```bash
OPENSEARCH_PASSWORD=... siem/apply-siem.sh
```

Dataset retention is declared in `siem/datasets.yml`.
