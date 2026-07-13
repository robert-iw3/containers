# Apache Cassandra

Apache **Cassandra 5.0** — a 3-node cluster on the official image with a declarative,
RF=3 schema, Kubernetes, and multi-host Ansible. The operational store for the
big-data integration demos (Kafka → Flink → **Cassandra**).

## Layout

```
cassandra/
├── docker-compose.yml            # 3-node cluster (sequential bootstrap) + schema-init
├── schema/schema.cql             # declarative RF=3 schema (telemetry keyspace)
├── scripts/apply_schema.sh       # apply schema.cql to a running cluster
├── k8s-cassandra-cluster.yaml    # StatefulSet (OrderedReady) + headless svc + PDB
├── tls/gen_cassandra_tls.sh      # self-signed CA + node keystore/truststore
├── ansible/                      # multi-host role (serial bootstrap) + molecule
├── tests/                        # pytest: cluster/env/schema/k8s invariants
└── archive/                      # superseded partial-config / Bitnami-coupled files
```

## Quick start (Compose)

```bash
docker compose up -d                       # 3-node cluster (give it a few minutes)
docker compose run --rm schema-init        # apply schema/schema.cql (RF=3)

docker exec -it cassandra_cassandra1_1 nodetool status    # 3x UN in dc1
```

The nodes bootstrap **sequentially** (node 2 waits for node 1, node 3 for node 2) as
Cassandra requires. Verified live: 3-node ring (all Up/Normal), the RF=3 schema
applies, and a `QUORUM` write on one node is read at `QUORUM` from another
(replication + consistency).

> The old deployment mounted a **partial** `cassandra.yaml` over the image's full
> config (nodes couldn't start) and used Bitnami-only env vars. This one drives the
> official image with its own `CASSANDRA_*` env vars — see `archive/`.

## Declarative schema

`schema/schema.cql` is the source of truth (idempotent `IF NOT EXISTS`). The
`telemetry` keyspace uses `NetworkTopologyStrategy {dc1: 3}`; `sensor_rollups` is
partitioned by sensor and clustered by window (newest first), TTL'd and
TimeWindowCompactionStrategy-tuned for time-series. Its columns match the Flink
pipeline's windowed output (`avg/min/max/count/stddev_value`, `anomaly`). Re-apply
with `./scripts/apply_schema.sh`.

## Kubernetes

```bash
kubectl apply -f k8s-cassandra-cluster.yaml
```

A `StatefulSet` with `podManagementPolicy: OrderedReady` (one node bootstraps at a
time), seeds pointing at the first pod's stable headless-service DNS, a readiness
probe that only passes once the node is Up/Normal in the ring, and a
**PodDisruptionBudget** (`minAvailable: 2`). Cassandra scales via `nodetool`
(streaming), so there's no naive HPA — adding/removing a node must stream data.

## Multi-host (Ansible)

`ansible/` deploys across hosts (`cassandra_cluster`); the first host is the seed and
the playbook uses `serial: 1` so nodes join one at a time. Set `cassandra_schema_src`
to apply the schema on the seed after it's up. The Molecule scenario converges a
1-node cluster, applies the schema, and verifies a CQL round-trip.

## TLS

`tls/gen_cassandra_tls.sh` builds a self-signed CA + node keystore/truststore (JKS).
Enable node-to-node and client encryption via `server_encryption_options` /
`client_encryption_options` (keystore/truststore paths + passwords) and mount `tls/`
into the containers. (Scripted here; wire it in for production.)

## Tests

```bash
pip install -r tests/requirements.txt
pytest tests/
```

Cluster/env invariants (official image, `CASSANDRA_*` not Bitnami, no partial-config
mount, sequential bootstrap), the RF=3 schema, and the k8s StatefulSet/PDB.
