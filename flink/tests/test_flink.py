"""
Tests for the Flink session-cluster deployment and the config-driven pipeline.

  * Config invariants (compose + k8s): the session-cluster wiring the previous
    deployment got wrong -- TaskManagers must know the JobManager RPC address, TLS
    must be enabled on both channels, the image/version must be consistent.
  * Pipeline generator logic: feed configs to build_pipeline and assert the emitted
    Flink SQL is well-formed for different data shapes/windows. (The live cluster run
    in the README is the full end-to-end check.)
"""

import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipelines"))
import build_pipeline  # noqa: E402

COMPOSE = (ROOT / "docker-compose.yml").read_text()
K8S = (ROOT / "k8s-flink-cluster.yaml").read_text()
IMAGE_TAG = "flink:2.3.0"


class TestComposeCluster:
    def test_uses_official_image_2_3(self):
        assert IMAGE_TAG in COMPOSE

    def test_jobmanager_rpc_address_set(self):
        # TaskManagers can't find the JobManager without this.
        assert "jobmanager.rpc.address: jobmanager" in COMPOSE

    def test_has_jobmanager_and_taskmanager(self):
        assert "command: jobmanager" in COMPOSE
        assert "command: taskmanager" in COMPOSE

    def test_tls_both_channels(self):
        assert "security.ssl.internal.enabled: true" in COMPOSE
        assert "security.ssl.rest.enabled: true" in COMPOSE

    def test_rest_healthcheck_is_https(self):
        assert "https://localhost:8081/overview" in COMPOSE

    def test_production_state_backend(self):
        assert "state.backend.type: rocksdb" in COMPOSE
        assert "execution.checkpointing.interval" in COMPOSE


class TestK8sCluster:
    def test_jobmanager_rpc_address_set(self):
        assert "jobmanager.rpc.address: flink-jobmanager" in K8S

    def test_taskmanager_hpa(self):
        assert "HorizontalPodAutoscaler" in K8S
        assert "name: flink-taskmanager" in K8S

    def test_tls_wired_and_https_probe(self):
        assert "security.ssl.internal.enabled: true" in K8S
        assert "scheme: HTTPS" in K8S

    def test_no_stale_version(self):
        assert "flink:2.0" not in K8S
        assert "flink:2.3.0" in K8S


class TestVersionConsistency:
    def test_config_and_readme_on_2_3(self):
        cfg = yaml.safe_load((ROOT / "flink_config.yaml").read_text())
        assert cfg["flink_version"] == "2.3.0"
        assert "2.0.0" not in (ROOT / "README.md").read_text()


# --- pipeline generator logic ---

TELEMETRY = {
    "name": "t",
    "source": {"connector": "datagen", "options": {"rows-per-second": "10"}},
    "schema": {
        "columns": [
            {"name": "sensor_id", "type": "INT", "datagen": {"kind": "random", "min": 1, "max": 5}},
            {"name": "value", "type": "DOUBLE", "datagen": {"kind": "random", "min": 0, "max": 9}},
        ],
        "time_attribute": "processing",
    },
    "key_by": ["sensor_id"],
    "window": {"type": "tumble", "size": "10 SECONDS"},
    "aggregations": [{"field": "value", "funcs": ["avg", "max", "count", "stddev_pop"]}],
    "anomaly": {"field": "value", "method": "zscore", "threshold": 3.0},
    "sink": {"connector": "print"},
}


class TestPipelineGenerator:
    def test_shipped_config_builds(self):
        cfg = yaml.safe_load((ROOT / "pipelines" / "pipeline_config.yaml").read_text())
        sql = build_pipeline.build(cfg)
        assert "CREATE TABLE source_stream" in sql
        assert "CREATE TABLE sink_stream" in sql
        assert "INSERT INTO sink_stream" in sql

    def test_tumble_tvf_and_proctime(self):
        sql = build_pipeline.build(TELEMETRY)
        assert "TUMBLE(TABLE source_stream, DESCRIPTOR(`proc_time`), INTERVAL '10' SECOND)" in sql
        assert "`proc_time` AS PROCTIME()" in sql

    def test_aggregations_and_anomaly_columns(self):
        sql = build_pipeline.build(TELEMETRY)
        for col in ("avg_value", "max_value", "count_value", "stddev_pop_value", "value_anomaly"):
            assert f"`{col}`" in sql
        assert "STDDEV_POP(`value`)" in sql

    def test_sink_schema_matches_projection(self):
        # Every projected alias must appear as a sink column declaration.
        cols = build_pipeline.projection(TELEMETRY)
        ddl = build_pipeline.sink_ddl(TELEMETRY, cols)
        for _, alias, _ in cols:
            assert f"`{alias}`" in ddl

    def test_hop_window_and_event_time(self):
        cfg = dict(TELEMETRY)
        cfg["window"] = {"type": "hop", "size": "30 SECONDS", "slide": "10 SECONDS"}
        cfg["schema"] = {
            "columns": [
                {"name": "value", "type": "DOUBLE"},
                {"name": "event_time", "type": "TIMESTAMP(3)"},
            ],
            "time_attribute": "event",
            "event_time_column": "event_time",
            "watermark_delay": "5 SECONDS",
        }
        cfg["key_by"] = []
        sql = build_pipeline.build(cfg)
        assert "HOP(TABLE source_stream, DESCRIPTOR(`event_time`), INTERVAL '10' SECOND, INTERVAL '30' SECOND)" in sql
        assert "WATERMARK FOR `event_time`" in sql

    def test_datagen_field_options_expanded(self):
        sql = build_pipeline.build(TELEMETRY)
        assert "'fields.sensor_id.min' = '1'" in sql
        assert "'fields.sensor_id.max' = '5'" in sql

    def test_example_configs_all_build(self):
        for cfg_file in (ROOT / "pipelines" / "examples").glob("*.yaml"):
            cfg = yaml.safe_load(cfg_file.read_text())
            assert "INSERT INTO sink_stream" in build_pipeline.build(cfg), cfg_file.name
