# Apache Flink

Apache **Flink 2.3** session cluster on Docker/Podman Compose, Kubernetes, or
multi-host Ansible, with TLS everywhere and a **config-driven streaming pipeline**
that processes whatever data you point it at — change a YAML file, not code.

Built on the official `flink:2.3.0` image (JobManager + autoscaling TaskManagers,
CeleryExecutor-free, Flink-native).

## Layout

```
flink/
├── docker-compose.yml         # session cluster: JobManager + scalable TaskManagers, TLS
├── k8s-flink-cluster.yaml     # Kubernetes: session cluster + TaskManager HPA + TLS
├── deploy_flink.py            # compose/kubernetes/ansible deploy wrapper
├── flink_config.yaml          # deployment config (method, version, TLS, sizing)
├── pipelines/                 # the config-driven streaming pipeline
│   ├── pipeline_config.yaml   #   declarative job: source, schema, window, aggs, sink
│   ├── build_pipeline.py      #   yaml -> Flink SQL generator
│   ├── run_pipeline.sh        #   generate SQL + submit to the cluster
│   └── examples/              #   more configs (e.g. clickstream) proving generality
├── tls/                       # gen_flink_tls.sh + JKS keystore/truststore (gitignored)
├── ansible/                   # multi-host role (JobManager + TaskManager groups) + molecule
├── tests/                     # pytest: cluster invariants + SQL-generator logic
└── archive/                   # superseded files (old custom image, split manifests)
```

## The config-driven pipeline

A streaming job is *described*, not coded. `build_pipeline.py` turns a declarative
config into a Flink SQL job — **source → windowed aggregation (+ optional anomaly
flag) → sink** — and the same generator handles any schema, source connector
(datagen/kafka/filesystem), window (tumbling/hopping/cumulate), aggregation set, and
sink. Point it at whatever data you need to process:

```yaml
source: {connector: datagen, options: {rows-per-second: "2000"}}
schema:
  columns:
    - {name: sensor_id, type: INT,    datagen: {kind: random, min: 1, max: 24}}
    - {name: value,     type: DOUBLE, datagen: {kind: random, min: 0, max: 250}}
  time_attribute: processing
key_by: [sensor_id]
window: {type: tumble, size: "10 SECONDS"}
aggregations: [{field: value, funcs: [avg, min, max, count, stddev_pop]}]
anomaly: {field: value, method: zscore, threshold: 3.0}
sink: {connector: print}
```

```bash
./pipelines/run_pipeline.sh pipelines/pipeline_config.yaml       # telemetry (tumbling)
./pipelines/run_pipeline.sh pipelines/examples/clickstream.yaml  # different shape, hop window
```

Both examples were verified running on the cluster, each producing its own windowed
output shape (per-key avg/min/max/count/stddev + anomaly flag) from datagen through
to the sink — no code changes between them. Swap `source`/`sink` to Kafka or the
filesystem for real ingest/egress (add the connector jar to the image for Kafka).

## Quick start (Compose)

```bash
bash tls/gen_flink_tls.sh                 # JKS keystore/truststore (self-signed)
docker compose up -d --scale taskmanager=3   # or: podman-compose up -d
./pipelines/run_pipeline.sh               # submit the default pipeline
```

- **UI / REST: https://localhost:8081** (TLS; self-signed cert → browser warning)
- Windowed output lands in the TaskManager logs (the `print` sink):
  `docker compose logs taskmanager | grep '+I\['`

## TLS

Both Flink SSL channels are on: **internal** (JobManager ↔ TaskManager RPC/data,
mutual auth) and **REST** (UI/API). `tls/gen_flink_tls.sh` builds one self-signed
JKS keystore + truststore (SANs cover the compose/k8s service names and localhost),
shared cluster-wide. Verified: the TaskManager registers over internal SSL, the REST
API serves HTTPS, plain HTTP is not served as cleartext, and jobs submit over TLS.
Replace the keystore with a CA-issued one for production.

## Kubernetes

```bash
bash tls/gen_flink_tls.sh
kubectl create secret generic flink-tls -n flink \
  --from-file=keystore.jks=tls/keystore.jks --from-file=truststore.jks=tls/truststore.jks
kubectl apply -f k8s-flink-cluster.yaml
```

Session cluster with shared config in a ConfigMap (`FLINK_PROPERTIES`, including the
`jobmanager.rpc.address` the TaskManagers need — the previous manifest omitted it).
The **TaskManager pool autoscales** via a `HorizontalPodAutoscaler` (CPU, 2–10,
drain-aware scale-down); Flink's adaptive scheduler spreads work onto new
TaskManagers as they register. For job-aware autoscaling, use the Flink Kubernetes
Operator's autoscaler.

## Multi-host (Ansible)

`ansible/` deploys across hosts: `flink_jobmanager` (JobManager) and
`flink_taskmanagers` (scale horizontally). The role generates the shared TLS keystore
on the JobManager and distributes it to the TaskManagers so internal SSL works
cluster-wide; TaskManagers reach the JobManager at its `flink_advertise_host`.

```bash
cd ansible && ansible-playbook -i inventory.ini deploy-flink.yml
```

A **Molecule** scenario (`roles/flink_node/molecule/default/`) converges JobManager +
TaskManager on one AlmaLinux systemd container and verifies the JobManager serves
HTTPS, the TaskManager registered (slots available), and plain HTTP isn't cleartext.

## Tests

```bash
pip install -r tests/requirements.txt
pytest tests/
```

Covers the cluster wiring invariants (JobManager RPC address, TLS on both channels,
version consistency, HPA) and the SQL generator's logic across window types, schemas,
event/processing time, and the shipped example configs.

## Deploy wrapper

```bash
python3 deploy_flink.py                    # method from flink_config.yaml (compose default)
python3 deploy_flink.py --action cleanup
```
