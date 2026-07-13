"""Tests for the Kafka KRaft deployment, declarative topics, and the producer.

  * Deployment invariants (compose + k8s): KRaft (no ZooKeeper), 3 nodes, RF=3 /
    min.insync.replicas=2, a shared cluster id, auto-topic-creation off.
  * Producer generators: each scenario emits the expected event shape.
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "producers"))
import produce  # noqa: E402

COMPOSE = (ROOT / "docker-compose.yml").read_text()
K8S = (ROOT / "k8s-kafka-cluster.yaml").read_text()


class TestComposeKRaft:
    def test_kraft_no_zookeeper(self):
        # No ZooKeeper service/image/ports/env (the comment may say "no ZooKeeper").
        assert "cp-zookeeper" not in COMPOSE
        assert "ZOOKEEPER_" not in COMPOSE
        assert ":2181" not in COMPOSE
        assert "KAFKA_PROCESS_ROLES: broker,controller" in COMPOSE
        assert "KAFKA_CONTROLLER_QUORUM_VOTERS" in COMPOSE

    def test_three_nodes(self):
        for n in ("kafka1", "kafka2", "kafka3"):
            assert f"{n}:" in COMPOSE

    def test_durability_defaults(self):
        assert "KAFKA_DEFAULT_REPLICATION_FACTOR: 3" in COMPOSE
        assert "KAFKA_MIN_INSYNC_REPLICAS: 2" in COMPOSE
        assert "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3" in COMPOSE

    def test_shared_cluster_id_and_no_autocreate(self):
        assert "CLUSTER_ID:" in COMPOSE
        assert 'KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"' in COMPOSE

    def test_official_image(self):
        assert "apache/kafka:4.3.1" in COMPOSE


class TestK8s:
    def test_statefulset_kraft(self):
        docs = [d for d in yaml.safe_load_all(K8S) if d]
        ss = [d for d in docs if d["kind"] == "StatefulSet"][0]
        args = ss["spec"]["template"]["spec"]["containers"][0]["args"][0]
        # per-pod NODE_ID derived from the ordinal
        assert "KAFKA_NODE_ID=$((ORD + 1))" in args
        assert ss["spec"]["serviceName"] == "kafka-headless"

    def test_has_pdb_and_headless(self):
        assert "PodDisruptionBudget" in K8S
        assert "clusterIP: None" in K8S

    def test_no_zookeeper(self):
        assert "zookeeper" not in K8S.lower()


class TestTopicsConfig:
    def test_topics_yaml_parses(self):
        cfg = yaml.safe_load((ROOT / "topics.yaml").read_text())
        names = {t["name"] for t in cfg["topics"]}
        assert {"pizza-orders", "user-behavior", "stock-ticks", "iot-metrics"} <= names
        for t in cfg["topics"]:
            assert t["replication_factor"] >= 1 and t["partitions"] >= 1


class TestProducer:
    def test_all_scenarios_have_generators(self):
        scenarios = yaml.safe_load((ROOT / "producers" / "scenarios.yaml").read_text())["scenarios"]
        for name, spec in scenarios.items():
            assert spec["generator"] in produce.GENERATORS, name
            assert "topic" in spec

    def test_telemetry_shape(self):
        key, event = produce.telemetry()
        assert set(event) == {"sensor_id", "metric", "value", "event_time"}
        assert event["sensor_id"] == key
        assert isinstance(event["value"], float)

    def test_each_generator_returns_key_and_dict(self):
        for gen in produce.GENERATORS.values():
            key, event = gen()
            assert isinstance(key, str) and isinstance(event, dict)
            assert "event_time" in event
