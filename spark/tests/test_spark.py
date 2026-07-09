"""Tests for the Spark cluster config and the telemetry pipeline.

Config/topology invariants always run. The pipeline-logic tests use a local
SparkSession and are skipped if pyspark isn't installed (the live cluster run in
the readme is the full end-to-end check).
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipelines"))


class TestClusterConfig:
    def test_all_images_share_one_tag(self):
        text = (ROOT / "docker-compose.yml").read_text()
        tags = set(re.findall(r"image:\s*spark-\w+:(\S+)", text))
        assert tags == {"4.1.2-hadoop3"}, tags

    def test_no_stale_spark_version_refs(self):
        for f in ["build.sh", "docker-compose.yml", "k8s-spark-cluster.yaml"]:
            assert "4.0.0-hadoop" not in (ROOT / f).read_text()

    def test_master_uses_host_not_removed_ip_flag(self):
        # --ip was removed in Spark 4.x; the master must use --host.
        master = (ROOT / "master" / "master.sh").read_text()
        assert "--host $SPARK_MASTER_HOST" in master
        assert "--ip $SPARK_MASTER_HOST" not in master

    def test_scala_213_for_spark4(self):
        pom = (ROOT / "examples" / "maven" / "pom.xml").read_text()
        assert "<scala.binary.version>2.13</scala.binary.version>" in pom
        sbt = (ROOT / "template" / "sbt" / "build.sbt").read_text()
        assert 'scalaVersion := "2.13' in sbt


class TestSparkDefaults:
    @pytest.fixture(scope="class")
    def conf(self):
        text = (ROOT / "base" / "spark-defaults.conf").read_text()
        return dict(
            line.split(None, 1)
            for line in text.splitlines()
            if line.strip() and not line.startswith("#")
        )

    def test_adaptive_query_execution_on(self, conf):
        assert conf["spark.sql.adaptive.enabled"].strip() == "true"

    def test_dynamic_allocation_autoscaling_on(self, conf):
        assert conf["spark.dynamicAllocation.enabled"].strip() == "true"
        assert conf["spark.dynamicAllocation.shuffleTracking.enabled"].strip() == "true"
        assert int(conf["spark.dynamicAllocation.maxExecutors"]) >= int(
            conf["spark.dynamicAllocation.minExecutors"])

    def test_event_log_enabled_for_history_server(self, conf):
        assert conf["spark.eventLog.enabled"].strip() == "true"


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("pyspark") is None,
    reason="pyspark not installed",
)
class TestPipelineLogic:
    @pytest.fixture(scope="class")
    def spark(self):
        from pyspark.sql import SparkSession
        s = SparkSession.builder.master("local[2]").appName("test").getOrCreate()
        yield s
        s.stop()

    def test_synthesize_row_count_and_devices(self, spark):
        import telemetry_pipeline as tp
        df = tp.synthesize(spark, rows=1000, devices=10)
        assert df.count() == 1000
        assert df.select("device_id").distinct().count() == 10
        assert set(r["metric"] for r in df.select("metric").distinct().collect()) <= {
            "temperature", "humidity", "pressure", "voltage"}

    def test_rollup_aggregates_correctly(self, spark):
        import telemetry_pipeline as tp
        from datetime import datetime
        rows = [
            ("d1", "temp", datetime(2026, 7, 9, 0, 0, 5), 10.0),
            ("d1", "temp", datetime(2026, 7, 9, 0, 0, 30), 20.0),
            ("d1", "temp", datetime(2026, 7, 9, 0, 0, 55), 30.0),
        ]
        df = spark.createDataFrame(rows, ["device_id", "metric", "event_time", "value"])
        agg = tp.rollup(df).collect()
        assert len(agg) == 1
        r = agg[0]
        assert r["count"] == 3 and r["avg"] == 20.0 and r["min"] == 10.0 and r["max"] == 30.0
