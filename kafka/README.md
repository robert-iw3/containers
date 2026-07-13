# Apache Kafka

Apache **Kafka 4.3** in **KRaft mode** (no ZooKeeper) — a 3-node combined
broker+controller cluster on the official `apache/kafka` image, with declarative
topics, a config-driven event producer, Kubernetes, and multi-host Ansible.

The event backbone for the big-data integration demos (see
`../integration_demos/`): producers → Kafka → Flink → Cassandra.

## Layout

```
kafka/
├── docker-compose.yml          # 3-node KRaft cluster (RF=3, min.insync=2) + topic-init
├── topics.yaml                 # declarative topics (applied by scripts/apply_topics.sh)
├── k8s-kafka-cluster.yaml      # KRaft StatefulSet + headless svc + PodDisruptionBudget
├── producers/                  # config-driven event generator (produce.py + scenarios.yaml)
├── scripts/apply_topics.sh     # create topics from topics.yaml (idempotent)
├── tls/gen_kafka_tls.sh        # self-signed CA + broker keystore for SSL
├── ansible/                    # multi-host KRaft role + molecule
├── tests/                      # pytest: KRaft/durability invariants + producer generators
├── helm/, integration_examples/, kafka-security-manager/   # existing extras (kept)
└── archive/                    # superseded ZooKeeper-based stack
```

## Quick start (Compose)

```bash
docker compose up -d                        # 3-node KRaft cluster
docker compose run --rm topic-init          # create topics from topics.yaml

# produce events (host venv: pip install -r producers/requirements.txt)
python3 producers/produce.py --scenario telemetry --bootstrap localhost:19092 --count 100000
```

- Bootstrap from the host: `localhost:19092` (kafka1), `:19093` (kafka2), `:19094` (kafka3)
- From containers on the `kafka` network: `kafka1:9092` etc.
- Verified live: 3-broker KRaft quorum forms, topics apply at RF=3/ISR=3, and a
  message produced to one broker is consumed from another (replication).

## Declarative topics

`topics.yaml` is the source of truth; `scripts/apply_topics.sh` creates any missing
topics (idempotent, `--if-not-exists`). `configs` is a comma-separated `k=v` list.

```yaml
topics:
  - {name: iot-metrics, partitions: 12, replication_factor: 3, configs: retention.ms=259200000}
```

## Config-driven producer

`producers/produce.py` emits JSON events for a named scenario in
`producers/scenarios.yaml` — different applications, different data, one producer:

| scenario | topic | event |
|---|---|---|
| `telemetry` | iot-metrics | `{sensor_id, metric, value, event_time}` (feeds the Flink→Cassandra demo) |
| `orders` | pizza-orders | `{order_id, shop_id, count, toppings, amount, ...}` |
| `clicks` | user-behavior | `{session_id, user_id, page, latency_ms, ...}` |
| `ticks` | stock-ticks | `{symbol, price, volume, ...}` |

Add a generator in `produce.py` + a scenario in `scenarios.yaml` to feed a new shape.

## Kubernetes

```bash
kubectl apply -f k8s-kafka-cluster.yaml
```

A `StatefulSet` of KRaft nodes: each pod derives its `NODE_ID` and advertised
listener from its ordinal, and the controller quorum is the stable headless-service
DNS of all pods. Ships a **PodDisruptionBudget** (`minAvailable: 2`). Kafka brokers
are stateful, so horizontal broker scaling means partition reassignment (Cruise
Control / Strimzi), not a naive HPA — in the big-data pipeline the autoscaled tier is
the Flink/Spark consumers.

## Multi-host (Ansible)

`ansible/` deploys a KRaft cluster across hosts (`kafka_cluster` group); each host
sets a unique `kafka_node_id`, and the role builds the controller quorum from all of
them. The Molecule scenario converges a 1-node cluster and verifies a full
produce/consume round-trip. Replication factors auto-cap to the node count so a
single node still forms a cluster.

## TLS (SSL)

`tls/gen_kafka_tls.sh` builds a self-signed CA + broker keystore/truststore. To
enable SSL, add an `SSL://` listener and the keystore env to each broker
(`KAFKA_SSL_KEYSTORE_LOCATION`, `..._PASSWORD`, `..._TRUSTSTORE_LOCATION`, …) and mount
`tls/` into the containers. The internal/controller listeners can stay on the private
network; expose the SSL listener to external clients. (Scripted here; not enabled in
the default demo compose to keep first-run friction low.)

## Tests

```bash
pip install -r tests/requirements.txt
pytest tests/
```

KRaft/durability invariants (no ZooKeeper, RF=3, min.insync=2, shared cluster id) for
compose + k8s, the topics config, and the producer generators.
