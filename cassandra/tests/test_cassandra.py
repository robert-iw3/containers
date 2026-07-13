"""Tests for the Cassandra cluster deployment and declarative schema.

Guards the wiring the old deployment got wrong: the official image driven by its own
CASSANDRA_* env vars (not a partial cassandra.yaml mounted over the full one, not
Bitnami-only vars), sequential bootstrap, RF=3 schema.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = (ROOT / "docker-compose.yml").read_text()
K8S = (ROOT / "k8s-cassandra-cluster.yaml").read_text()
SCHEMA = (ROOT / "schema" / "schema.cql").read_text()


class TestComposeCluster:
    def test_official_image_5(self):
        assert "cassandra:5.0" in COMPOSE

    def test_three_nodes(self):
        for n in ("cassandra1", "cassandra2", "cassandra3"):
            assert f"{n}:" in COMPOSE

    def test_official_env_not_bitnami(self):
        assert "CASSANDRA_CLUSTER_NAME" in COMPOSE
        assert "CASSANDRA_SEEDS" in COMPOSE
        assert "CASSANDRA_ENDPOINT_SNITCH" in COMPOSE
        # Bitnami-only vars that the official image ignores must be gone.
        assert "CASSANDRA_PASSWORD_SEEDER" not in COMPOSE

    def test_no_partial_config_mount(self):
        # The bug: mounting a partial cassandra.yaml over the image's full config.
        assert "/etc/cassandra/cassandra.yaml" not in COMPOSE

    def test_sequential_bootstrap(self):
        # node2 waits for node1, node3 waits for node2.
        assert "cassandra1:\n        condition: service_healthy" in COMPOSE or \
               "cassandra1: {condition: service_healthy}" in COMPOSE
        assert "cassandra2:" in COMPOSE

    def test_schema_init_service(self):
        assert "schema-init:" in COMPOSE


class TestSchema:
    def test_keyspace_rf3(self):
        assert "NetworkTopologyStrategy" in SCHEMA
        assert re.search(r"'dc1'\s*:\s*3", SCHEMA)

    def test_rollup_table_and_twcs(self):
        assert "telemetry.sensor_rollups" in SCHEMA
        assert "TimeWindowCompactionStrategy" in SCHEMA

    def test_columns_match_flink_output(self):
        # The Flink pipeline writes these rollup columns.
        for col in ("avg_value", "min_value", "max_value", "count_value", "stddev_value", "anomaly"):
            assert col in SCHEMA


class TestK8s:
    def test_statefulset_ordered_bootstrap(self):
        docs = [d for d in yaml.safe_load_all(K8S) if d]
        ss = [d for d in docs if d["kind"] == "StatefulSet"][0]
        assert ss["spec"]["podManagementPolicy"] == "OrderedReady"
        assert ss["spec"]["serviceName"] == "cassandra"

    def test_headless_and_pdb(self):
        assert "clusterIP: None" in K8S
        assert "PodDisruptionBudget" in K8S

    def test_seeds_use_stable_dns(self):
        assert "cassandra-0.cassandra" in K8S
