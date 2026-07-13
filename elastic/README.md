# Elastic SIEM — production deployment

A TLS-secured, security-enabled Elastic Stack (Elasticsearch + Kibana + Fleet) built
for SIEM: Fleet agents stream parsed data into **labeled per-dataset indices** with
**ILM** lifecycle management. One config drives **any topology** across compose,
Kubernetes, multi-host Ansible, or plain SSH. See **`demo.md`** for the local
single-host stack test (bring-up, Kibana, Fleet, agent enrollment, Suricata/Zeek/
Defend integrations, teardown).

## Configurable deployment (the one manifest that initiates any deployment)

`stack.config.yml` + `gen_stack.py` render a correct compose for any size:

```yaml
elasticsearch: {nodes: 3, heap: auto}   # 1-7 nodes; auto = 50% RAM / nodes, capped 31g
kibana:        {nodes: 1}               # 1-2 search heads
fleet: true                             # Fleet Server (agents -> labeled indices)
logstash: false
tls: true
```

```bash
cp .env.example .env      # set ELASTIC_PASSWORD, KIBANA_SYSTEM_PASSWORD
python3 gen_stack.py > docker-compose.generated.yml
docker compose -f docker-compose.generated.yml up -d
```

The generated `setup` service mints a CA + per-node certs for exactly the instances
it renders, so TLS is correct at any size. **Live-verified**: a generated 3-ES + 1-
Kibana stack forms a **green** cluster over TLS with `kibana_system` auth.

Hand-written variants are still here too: `docker-compose.yml` (single node),
`docker-compose-multi-node.yml` (fixed 3-node), `docker-compose-no-tls.yml`.

## Host prep (balance security ↔ performance)

Elasticsearch needs kernel/limits tuning. Run on each ES/Kibana host **before**
deploying; it snapshots the originals so you can restore exactly:

```bash
sudo bash host-prep/prepare-host.sh          # apply (max_map_count, swappiness=1, THP=never, memlock/nofile)
sudo bash host-prep/prepare-host.sh --check  # report only
sudo bash host-prep/prepare-host.sh --revert # restore from snapshot
```

`heap: auto` sizes the JVM from discovered RAM (50% ÷ nodes-per-host, capped at the
31g compressed-oops threshold) with a matching container `mem_limit`.

## Multi-host — Ansible OR plain SSH

- **Ansible**: `ansible/` role (`playbook.yml`, inventories for docker/podman/k8s).
- **SSH (no Ansible)**: `ssh-deploy/` — edit `cluster.hosts` (`<role> <user@host>
  <advertise-ip>`, e.g. 3-7 `es` + 2 `kibana`), then
  `ELASTIC_PASSWORD=… KIBANA_SYSTEM_PASSWORD=… ./ssh-deploy/deploy-cluster.sh`. It
  mints the CA + per-node certs, preps each host, pushes certs + `node-up.sh`, starts
  each node wired into the cluster over TLS, and sets the `kibana_system` password.

## Kubernetes (autoscaling)

`kubernetes/elastic-k8s.yml`: Elasticsearch **StatefulSet** (3, TLS, memlock,
`vm.max_map_count` init container) + **PodDisruptionBudget**; **Kibana** Deployment
(2 search heads) behind an **HPA**. ES data nodes are stateful — scale via the ES
autoscaling API / ECK operator, not a naive HPA — so only the stateless Kibana tier
autoscales here. Create the `elastic-certs` + `elastic-credentials` secrets first
(header comment has the commands).

## SIEM — labeled indices + ILM

`siem/datasets.yml` describes each dataset; `gen_siem.py` renders, per dataset, an
ILM policy (**hot → warm → delete**) and a **data-stream index template** that routes
it into the labeled index `logs-<dataset>-<namespace>`:

```bash
ES=https://localhost:9200 ELASTIC_PASSWORD=… CA=certs/ca/ca.crt ./siem/apply-siem.sh
```

Ships `siem.auth` (90d), `siem.network` (30d), `siem.endpoint` (180d), `siem.cloud`
(365d), each `best_compression`. Add a dataset → re-apply; Fleet integrations writing
to `logs-<dataset>-*` inherit the policy + template automatically.

## Tests

```bash
pip install -r tests/requirements.txt && pytest tests/
```
Covers the compose fixes, the generator (topologies/auto-heap/shell-safety), SIEM
ILM + labeled templates, the k8s manifest, host-prep, and the SSH scripts.
