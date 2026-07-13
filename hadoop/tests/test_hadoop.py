"""Tests for the Hadoop datalake cluster deployment and the log-processing job.

Guards the bugs the analysis found (the base image silently built empty on
debian:13; single datanode; stale Makefile) and the multi-format log parser.
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "datalake" / "jobs"))
import parse_logs_mapper as mapper  # noqa: E402

DOCKERFILE = (ROOT / "base" / "Dockerfile").read_text()
COMPOSE = (ROOT / "docker-compose.yml").read_text()
ENV = (ROOT / "hadoop.env").read_text()
K8S = (ROOT / "k8s-hadoop-cluster.yaml").read_text()
MAKEFILE = (ROOT / "Makefile").read_text()


class TestBaseImage:
    def test_jdk17_on_debian12(self):
        # debian:13 dropped JDK 11/17; the old Dockerfile silently built an empty image.
        assert "FROM docker.io/debian:12" in DOCKERFILE
        assert "openjdk-17-jdk-headless" in DOCKERFILE
        assert "java-17-openjdk" in DOCKERFILE

    def test_run_fails_fast(self):
        # set -eux so a failed apt/download aborts instead of exiting 0 with no Hadoop.
        assert "set -eux" in DOCKERFILE

    def test_env_split_for_podman_expansion(self):
        # HADOOP_HOME must be its own ENV so ${HADOOP_VERSION} expands under podman.
        assert "ENV HADOOP_HOME=/opt/hadoop-${HADOOP_VERSION}" in DOCKERFILE
        assert DOCKERFILE.count("\nENV ") >= 8

    def test_python3_for_streaming(self):
        assert "python3" in DOCKERFILE


class TestCompose:
    def test_three_datanodes_two_nodemanagers(self):
        d = yaml.safe_load(COMPOSE)
        svc = d["services"]
        assert {"datanode1", "datanode2", "datanode3"} <= set(svc)
        assert {"nodemanager1", "nodemanager2"} <= set(svc)

    def test_replication_three(self):
        assert "HDFS_CONF_dfs_replication=3" in ENV

    def test_images_tagged_latest(self):
        # compose references :latest; the Makefile must build :latest (not :branch).
        assert "hadoop-namenode:latest" in COMPOSE
        assert "hadoop-base:latest" in MAKEFILE
        assert "current_branch" not in MAKEFILE
        assert "hadoop-3.4.1" not in MAKEFILE   # stale path removed


class TestK8s:
    def test_datalake_topology(self):
        docs = [d for d in yaml.safe_load_all(K8S) if d]
        dn = [d for d in docs if d["kind"] == "StatefulSet" and d["metadata"]["name"] == "datanode"][0]
        assert dn["spec"]["replicas"] == 3
        assert any(d["kind"] == "PodDisruptionBudget" for d in docs)
        # nodemanager (stateless) autoscales; HDFS does not.
        assert any(d["kind"] == "HorizontalPodAutoscaler" for d in docs)


class TestAnsible:
    def test_role_and_groups(self):
        tasks = (ROOT / "ansible/roles/hadoop_node/tasks/main.yml").read_text()
        # role runs each Hadoop role by inventory group membership
        for g in ("hadoop_namenode", "hadoop_datanodes", "hadoop_resourcemanager",
                  "hadoop_nodemanagers", "hadoop_historyserver"):
            assert g in tasks, g
        inv = (ROOT / "ansible/inventory.ini").read_text()
        assert "[hadoop_datanodes]" in inv and "hadoop-worker-1" in inv

    def test_env_points_at_resolved_hosts(self):
        tasks = (ROOT / "ansible/roles/hadoop_node/tasks/main.yml").read_text()
        assert "hdfs://{{ namenode_host }}" in tasks
        assert "yarn_resourcemanager_hostname" in tasks


class TestNginx:
    def test_namenode_ui_port_is_hadoop3(self):
        # Optional UI-theming proxy: must target the Hadoop 3.x NameNode UI (9870),
        # not the stale Hadoop 2.x port (50070).
        conf = (ROOT / "nginx" / "default.conf").read_text()
        assert "namenode:9870" in conf
        assert "50070" not in conf


class TestLogParser:
    def test_json(self):
        assert mapper.classify('{"level":"ERROR","service":"api","msg":"x"}') == ("api", "ERROR")

    def test_apache_combined_by_status(self):
        assert mapper.classify('1.2.3.4 - - [13/Jul/2026:02:01:12 +0000] "GET /x HTTP/1.1" 500 512 "-" "ua"') == ("web", "ERROR")
        assert mapper.classify('1.2.3.4 - - [13/Jul/2026:02:01:12 +0000] "GET /x HTTP/1.1" 200 512 "-" "ua"') == ("web", "INFO")

    def test_csv(self):
        assert mapper.classify("2026-07-13T02:03:02Z,ERROR,scheduler,job failed") == ("scheduler", "ERROR")

    def test_syslog(self):
        src, lvl = mapper.classify("<34>Jul 13 02:02:01 node1 sshd[2211]: Failed password for root")
        assert src == "sshd" and lvl == "ERROR"

    def test_unknown_fallback(self):
        assert mapper.classify("just some random text") == ("unknown", "UNKNOWN")

    def test_end_to_end_counts(self):
        # Mapper over the sample logs, reduced -> expected (source::level) counts.
        import subprocess
        logs = b"".join((ROOT / "datalake" / "sample_logs").glob("*.log").__iter__() and
                         [p.read_bytes() for p in (ROOT / "datalake" / "sample_logs").glob("*.log")])
        m = subprocess.run([sys.executable, str(ROOT / "datalake/jobs/parse_logs_mapper.py")],
                           input=logs, capture_output=True)
        rows = sorted(m.stdout.decode().splitlines())
        red = subprocess.run([sys.executable, str(ROOT / "datalake/jobs/count_reducer.py")],
                             input=("\n".join(rows) + "\n").encode(), capture_output=True)
        out = dict(line.split("\t") for line in red.stdout.decode().splitlines())
        assert out["web::INFO"] == "2"      # two 2xx access-log lines
        assert "api::ERROR" in out
