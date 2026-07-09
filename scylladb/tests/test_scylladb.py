"""Unit tests for the ScyllaDB telemetry pipeline.

Hermetic (no live cluster): schema-template rendering + TWCS window math, ETL
rollup aggregation via a fake session, and config validation. The live
end-to-end pipeline load test lives in load_test.py.
"""
import sys
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl"))


def render_schema(config):
    env = Environment(
        loader=FileSystemLoader(str(ROOT / "schema" / "templates")),
        trim_blocks=True, lstrip_blocks=True,
    )
    return env.get_template("schema.cql.j2").render(**config)


class TestSchemaTemplate:
    def test_example_config_renders(self):
        cfg = yaml.safe_load(open(ROOT / "schema" / "schema.yaml.example"))
        cql = render_schema(cfg)
        assert "CREATE KEYSPACE IF NOT EXISTS telemetry" in cql
        assert "CREATE TABLE IF NOT EXISTS telemetry.raw_events" in cql
        assert "PRIMARY KEY ((device_id, bucket), event_time, event_id)" in cql

    def test_timeseries_profile_gets_twcs(self):
        cfg = yaml.safe_load(open(ROOT / "schema" / "schema.yaml.example"))
        cql = render_schema(cfg)
        assert "TimeWindowCompactionStrategy" in cql
        assert "ZstdCompressor" in cql

    def test_registry_profile_has_no_twcs(self):
        cfg = {
            "keyspaces": [{
                "name": "k", "replication": {"class": "SimpleStrategy", "replication_factor": 1},
                "tables": [{
                    "name": "reg", "profile": "registry",
                    "columns": [{"name": "id", "type": "text"}],
                    "partition_key": ["id"],
                }],
            }]
        }
        cql = render_schema(cfg)
        assert "CREATE TABLE IF NOT EXISTS k.reg" in cql
        assert "TimeWindowCompactionStrategy" not in cql

    @pytest.mark.parametrize("ttl_days,expect", [
        (30, "'compaction_window_unit': 'DAYS', 'compaction_window_size': 1"),   # 30/45<1 -> 1
        (90, "'compaction_window_unit': 'DAYS', 'compaction_window_size': 2"),   # ceil(90/45)=2
        (1, "'compaction_window_unit': 'HOURS'"),                                # <=2d -> hours
    ])
    def test_twcs_window_stays_under_50(self, ttl_days, expect):
        cfg = {
            "keyspaces": [{
                "name": "k", "replication": {"class": "SimpleStrategy", "replication_factor": 1},
                "tables": [{
                    "name": "ts", "profile": "timeseries", "ttl_seconds": ttl_days * 86400,
                    "columns": [{"name": "id", "type": "text"}, {"name": "t", "type": "timestamp"}],
                    "partition_key": ["id"], "clustering_key": ["t"],
                }],
            }]
        }
        cql = render_schema(cfg)
        assert expect in cql
        # verify the resulting window count never exceeds Scylla's cap of 50
        import re
        unit = re.search(r"'compaction_window_unit': '(\w+)'", cql).group(1)
        size = int(re.search(r"'compaction_window_size': (\d+)", cql).group(1))
        window_seconds = size * (3600 if unit == "HOURS" else 86400)
        assert (ttl_days * 86400) / window_seconds <= 50

    def test_multi_dc_replication(self):
        cfg = {
            "keyspaces": [{
                "name": "k",
                "replication": {"class": "NetworkTopologyStrategy",
                                "datacenters": {"dc1": 3, "dc2": 3}},
                "tables": [{"name": "t", "profile": "registry",
                            "columns": [{"name": "id", "type": "text"}],
                            "partition_key": ["id"]}],
            }]
        }
        cql = render_schema(cfg)
        assert "'dc1': '3'" in cql and "'dc2': '3'" in cql


class FakeRow:
    def __init__(self, device_id, metric, value, event_time, payload=None):
        self.device_id, self.metric, self.value = device_id, metric, value
        self.event_time, self.payload = event_time, payload


class FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.writes = []

    def execute(self, query, params=None):
        if query.strip().upper().startswith("SELECT"):
            return list(self._rows)
        self.writes.append((query, params))
        return []


class TestEtlRollup:
    def test_aggregates_by_device_metric_minute(self):
        import worker
        from datetime import datetime, timezone
        t = datetime(2026, 7, 9, 0, 30, 15, tzinfo=timezone.utc)
        rows = [
            FakeRow("d1", "temp", 10.0, t),
            FakeRow("d1", "temp", 20.0, t),
            FakeRow("d1", "temp", 30.0, t),
            FakeRow("d2", "temp", 5.0, t),
        ]
        session = FakeSession(rows)
        written = worker.rollup_once(session)
        assert written == 2  # (d1,temp,minute) and (d2,temp,minute)
        d1_write = next(w for w in session.writes if "metrics_1m" in w[0] and w[1][0] == "d1")
        # params: device, metric, day, minute, count, sum, min, max, avg
        _, _, _, _, count, s, mn, mx, avg = d1_write[1]
        assert count == 3 and s == 60.0 and mn == 10.0 and mx == 30.0 and avg == 20.0

    def test_null_value_routes_to_dead_letter(self):
        import worker
        from datetime import datetime, timezone
        t = datetime(2026, 7, 9, 0, 30, tzinfo=timezone.utc)
        session = FakeSession([FakeRow("d1", "temp", None, t, payload='{"raw":1}')])
        written = worker.rollup_once(session)
        assert written == 0
        assert any("dead_letter" in w[0] for w in session.writes)


class TestConfigValidation:
    def test_compose_has_three_scylla_nodes(self):
        compose = yaml.safe_load(open(ROOT / "docker-compose.yml"))
        nodes = [s for s in compose["services"] if s.startswith("scylla-node")]
        assert len(nodes) == 3

    def test_every_scylla_node_seeds_node1(self):
        compose = yaml.safe_load(open(ROOT / "docker-compose.yml"))
        for name in ("scylla-node1", "scylla-node2", "scylla-node3"):
            assert "--seeds=scylla-node1" in compose["services"][name]["command"]

    def test_api_and_etl_wait_for_schema(self):
        compose = yaml.safe_load(open(ROOT / "docker-compose.yml"))
        for svc in ("api", "etl"):
            dep = compose["services"][svc]["depends_on"]
            assert dep["schema-init"]["condition"] == "service_completed_successfully"
