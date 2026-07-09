## scylladb

A ScyllaDB deployment ***demo*** for IoT / data-pipeline telemetry: a 3-node
cluster (RF=3) with a config-driven schema, a REST API any app or frontend
connects to, an ETL rollup worker, and autoscaling — handling both structured
readings and unstructured JSON/blob payloads at scale.

### What's here

```console
scylladb/
├── docker-compose.yml       # 3-node cluster + schema-init + API + ETL (verified end to end)
├── schema/
│   ├── telemetry.cql        # IoT telemetry schema, TWCS-tuned for time-series
│   ├── schema.yaml.example  # config-driven schema for ANY data shape
│   └── templates/           # Jinja → CQL generator (performance profiles baked in)
├── api/                     # FastAPI telemetry service (token-aware/DC-aware driver)
├── etl/                     # rollup worker: raw_events → per-minute aggregates
├── k8s-scylladb.yaml        # ScyllaDB Operator ScyllaCluster (3 members, scalable)
├── k8s-telemetry-app.yaml   # API Deployment + HPA autoscaling + ETL, on k8s
├── ansible/                 # multi-host deploy playbooks
├── deploy_scylladb.py       # one orchestrator across docker / k8s / ansible
└── tests/                   # pytests + live end-to-end bulk load test
```

### Quick start (docker)

```bash
docker compose up -d          # 3 nodes join one at a time, schema loads, API+ETL start
curl localhost:8000/health    # {"status":"ok"} once the cluster is up
```

Ingest and query through the API — no CQL knowledge needed:

```bash
# structured reading + unstructured payload in one call
curl -XPOST localhost:8000/events -H 'content-type: application/json' -d \
  '{"device_id":"sensor-42","metric":"temperature","value":21.5,"unit":"C","payload":{"loc":"warehouse"}}'

curl localhost:8000/events/sensor-42                  # read back
curl localhost:8000/metrics/sensor-42/temperature     # ETL-rolled per-minute aggregates
```

Endpoints: `POST /events`, `POST /events/bulk`, `GET /events/{device}`,
`GET /events/{device}/count`, `GET /metrics/{device}/{metric}`,
`POST /devices`, `GET /devices`, `GET /health`.

### Configuration for any data (schema templates)

`schema/schema.yaml.example` defines keyspaces/tables declaratively; the Jinja
template renders CQL and applies a **performance profile** per table so tuning is
never hand-copied:

- `profile: timeseries` → TimeWindowCompactionStrategy with the window auto-sized
  from the TTL (kept under Scylla's `twcs_max_window_count` of 50), Zstd
  compression, short `gc_grace`, percentile speculative retry.
- `profile: registry` → plain table for lookups.

Model IoT, events, documents, or metrics by editing the YAML — every table can
carry an unstructured `text` column for arbitrary payloads alongside its typed
columns.

### At-scale performance, baked in

- **Time-series compaction (TWCS)**: append-only telemetry ages out whole
  SSTables with the TTL instead of being rewritten — flat write amplification at
  high ingest, cheap expiry.
- **Token-aware + DC-aware routing** in the API driver: each request goes
  straight to a replica owning the partition, staying in the local DC.
- **`LOCAL_QUORUM`** reads and writes by default: survives a node loss without
  cross-DC latency.
- **Bounded partitions**: raw events are partitioned by `(device_id, hour)` so no
  partition grows unbounded under high-rate streams.
- **Concurrent bulk ingest** (`/events/bulk`) with prepared statements.

### Autoscaling

- **API tier** (stateless) autoscales on CPU/memory via the HorizontalPodAutoscaler
  in `k8s-telemetry-app.yaml` (3→20 replicas).
- **ScyllaDB** (stateful) scales by raising the ScyllaCluster rack `members` in
  `k8s-scylladb.yaml`; the Scylla Operator adds a node and streams data to it. Add
  racks for rack-aware placement or datacenters for geo-distribution — the
  keyspace already uses `NetworkTopologyStrategy`.

### Verified end to end

`tests/load_test.py` drives the live pipeline — small (100), medium (5k), and
large (50k) synthetic datasets are ingested through the API in bulk, then queried
back to prove every event was stored (RF-replicated) and is accessible:

```bash
docker compose up -d
API_URL=http://localhost:8000 python tests/load_test.py all
# small/medium/large: PASS — 55,100 events stored and verified
```

`tests/test_scylladb.py` covers schema-template rendering (incl. the TWCS window
math), ETL rollup aggregation, and compose/topology invariants:

```bash
pip install -r tests/requirements.txt && pytest tests/test_scylladb.py
```

### Multi-host / production

`deploy_scylladb.py` renders the schema from config and drives docker, Kubernetes
(operator), or Ansible from one `config/user_config.yaml`.

- **Kubernetes**: install the operator, then
  `kubectl apply -f k8s-scylladb.yaml -f k8s-telemetry-app.yaml`.
- **Ansible**: `ansible-playbook -i ansible/inventory.ini ansible/playbooks/deploy-sharded.yml`.

### Security

Auth (PasswordAuthenticator + CassandraAuthorizer) is on; supply real
credentials via the k8s Secret / Vault rather than the demo `cassandra`
account, and enable TLS (`tls_enabled` + certs) for any non-local deployment.
