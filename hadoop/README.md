# Apache Hadoop — distributed datalake

Apache **Hadoop 3.5** as a distributed data cluster: **HDFS** (NameNode + 3 DataNodes,
RF=3) as the datalake storage layer and **YARN** (ResourceManager + 2 NodeManagers)
for compute, with a config-templated image (`CORE_CONF_*/HDFS_CONF_*/YARN_CONF_*`
env → Hadoop XML). Built for massive telemetry and heterogeneous log/unstructured
data: a `raw → curated` datalake with a distributed multi-format log-processing job.

## Layout

```
hadoop/
├── base/                     # base image (Hadoop 3.5 + JDK17 + python3) + entrypoint
├── namenode|datanode|resourcemanager|nodemanager|historyserver/   # role images
├── docker-compose.yml        # NameNode + 3 DataNodes + RM + 2 NodeManagers + history
├── hadoop.env                # cluster config (RF=3, YARN scheduler, compression, …)
├── k8s-hadoop-cluster.yaml   # HDFS StatefulSets + YARN + NodeManager HPA + PDB
├── datalake/                 # the datalake + log-processing pipeline
│   ├── sample_logs/          #   JSON / Apache-combined / syslog / CSV samples
│   ├── jobs/                 #   Hadoop Streaming mapper + reducer (multi-format parse)
│   ├── init_datalake.sh      #   create HDFS zones (raw/curated/warehouse) + load logs
│   └── process_logs.sh       #   run the distributed log-processing job on YARN
├── Makefile                  # make build | up | down | datalake
└── tests/                    # pytest: image/compose/k8s invariants + log-parser logic
```

## Quick start

```bash
make build                 # build the images (:latest)
docker compose up -d       # NameNode + 3 DataNodes + RM + 2 NodeManagers + history
make datalake              # create datalake zones, load logs, run the processing job
```

UIs: NameNode http://localhost:9870 · ResourceManager http://localhost:8088

## Datalake + distributed log processing

The datalake is laid out on HDFS as `raw/` (landing) → `curated/` (processed) →
`warehouse/` (serving), replicated 3× across the DataNodes.

`datalake/process_logs.sh` runs a **Hadoop Streaming** job on YARN that turns
heterogeneous, unstructured logs into a structured analytics rollup:

- **input** — `/datalake/raw/logs/` holds four formats at once: JSON application logs,
  Apache-combined access logs, syslog, and CSV.
- **mapper** (`jobs/parse_logs_mapper.py`) — parses each line regardless of format
  into a common `(source, level)` and emits `source::level → 1`. Apache lines are
  levelled by status code; syslog by content.
- **reducer** (`jobs/count_reducer.py`) — sums per `(source, level)`.
- **output** — `/datalake/curated/log_summary` (e.g. `api::ERROR 1`, `web::INFO 2`).

Because it's Streaming on YARN, the parse/aggregate runs **distributed across the
NodeManagers** — the model scales to massive telemetry/log volumes (add DataNodes for
storage, NodeManagers for compute). Add a format by extending `classify()` in the
mapper; point `init_datalake.sh` at real log sources to ingest your own.

## Kubernetes

`k8s-hadoop-cluster.yaml` runs HDFS as StatefulSets (NameNode; 3-replica DataNode +
PodDisruptionBudget) and YARN as Deployments, all fed by the `hadoop-config`
ConfigMap. The **NodeManager (stateless compute) tier autoscales** via an HPA;
HDFS/DataNodes are stateful (scale by adding nodes + rebalancing, not an HPA). Build
and push the `hadoop-*:latest` images to your registry first.
## Multi-host (Ansible)

`ansible/` deploys a genuinely distributed cluster across hosts by role group —
`hadoop_namenode`, `hadoop_datanodes`, `hadoop_resourcemanager`,
`hadoop_nodemanagers`, `hadoop_historyserver` (a host may be in several). The role
resolves the NameNode/RM/History addresses from the inventory and points every
node's config env at them. Push the `hadoop-*:latest` images to a registry
(`hadoop_registry`) or preload them, then:

```bash
cd ansible && ansible-playbook -i inventory.ini deploy-hadoop.yml
```

A Molecule scenario is included (converge the whole cluster on one instance + verify
HDFS/YARN) — run it in CI or on a host with a few GB free; Hadoop is heavy.

## Optional: themed UI proxy

`nginx/` is an optional reverse proxy that injects CSS over the NameNode UI (not in
the default compose). Its upstream is `9870`; add an `nginx` service building
`./nginx` if you want the themed page.
