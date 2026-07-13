"""Tests for the Elastic SIEM deployment: the config-driven stack generator, the
multi-node compose fixes, host-prep, SIEM ILM/labeled-indices, k8s, and SSH deploy.
"""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "siem"))
import gen_stack  # noqa: E402
import gen_siem  # noqa: E402

MULTI = (ROOT / "docker-compose-multi-node.yml").read_text()
K8S = (ROOT / "kubernetes" / "elastic-k8s.yml").read_text()
HOSTPREP = (ROOT / "host-prep" / "prepare-host.sh").read_text()


def cfg(nodes=3, kib=1, fleet=True, logstash=False, tls=True, heap="512m", memlock=True):
    return {
        "cluster_name": "elastic-cluster",
        "elasticsearch": {"nodes": nodes, "heap": heap},
        "kibana": {"nodes": kib},
        "fleet": fleet, "logstash": logstash, "tls": tls,
        "performance": {"memory_lock": memlock},
    }


class TestMultiNodeComposeFixes:
    def test_memlock_and_setup_dep(self):
        d = yaml.safe_load(MULTI)["services"]
        for n in ("elasticsearch", "elasticsearch1", "elasticsearch2"):
            assert d[n]["ulimits"]["memlock"]["soft"] == -1, n
            assert "setup" in d[n]["depends_on"], n
        # setup must NOT depend on elasticsearch (that deadlocks) and not be profiled
        assert "depends_on" not in d["setup"]
        assert "profiles" not in d["setup"]

    def test_no_single_node_discovery_in_multi(self):
        # the single-node elasticsearch.yml must not be mounted into the multi cluster
        assert "elasticsearch-multi.yml" in MULTI
        multi_cfg = yaml.safe_load((ROOT / "elasticsearch" / "config" / "elasticsearch-multi.yml").read_text())
        assert "discovery.type" not in multi_cfg          # single-node discovery would break the cluster
        assert multi_cfg.get("xpack.security.authc.api_key.enabled") is True


class TestStackGenerator:
    def test_topology_counts(self):
        for n_es, n_kb, fleet, logstash in [(1, 1, False, False), (5, 2, True, True), (7, 2, True, False)]:
            s = gen_stack.build(cfg(n_es, n_kb, fleet, logstash))["services"]
            assert len([k for k in s if k.startswith("es")]) == n_es
            assert len([k for k in s if k.startswith("kibana")]) == n_kb
            assert ("fleet-server" in s) == fleet
            assert ("logstash" in s) == logstash

    def test_discovery_and_tls(self):
        s = gen_stack.build(cfg(3))["services"]
        assert s["es01"]["environment"]["cluster.initial_master_nodes"] == "es01,es02,es03"
        assert s["es01"]["environment"]["discovery.seed_hosts"] == "es02,es03"
        assert s["es01"]["environment"]["xpack.security.http.ssl.enabled"] == "true"

    def test_tls_off_removes_ssl(self):
        s = gen_stack.build(cfg(1, tls=False))["services"]
        assert "xpack.security.http.ssl.enabled" not in s["es01"]["environment"]

    def test_auto_heap_and_mem_limit(self):
        # auto = 50% RAM / nodes, capped 31g, floored 512m
        assert gen_stack.compute_heap({"elasticsearch": {"heap": "auto"}}, 1000) == "512m"
        assert gen_stack.mem_limit_for("2g") == "4096m"
        s = gen_stack.build(cfg(3, heap="512m"))["services"]
        assert s["es01"]["mem_limit"] == "1024m"

    def test_setup_command_shell_safe(self):
        # the setup command is a single-quoted bash -c: exactly 2 single quotes,
        # flow-style instances.yml, and $$n-escaped loop var
        cmd = gen_stack.build(cfg(3))["services"]["setup"]["command"]
        assert cmd.count("'") == 2
        assert "dns: [es01, localhost]" in cmd
        assert "$$n" in cmd
        assert 'printf "%b"' in cmd

    def test_memory_lock_toggle(self):
        assert gen_stack.build(cfg(1, memlock=False))["services"]["es01"]["environment"]["bootstrap.memory_lock"] == "false"
        assert gen_stack.build(cfg(1, memlock=True))["services"]["es01"]["environment"]["bootstrap.memory_lock"] == "true"


class TestSiemIlm:
    def test_ilm_phases_and_retention(self):
        ds = {"name": "siem.auth", "retention_days": 90, "warm_after_days": 7}
        pol = gen_siem.ilm_policy(ds)["policy"]["phases"]
        assert set(pol) == {"hot", "warm", "delete"}
        assert pol["delete"]["min_age"] == "90d"
        assert "rollover" in pol["hot"]["actions"]

    def test_labeled_index_template(self):
        ds = {"name": "siem.network", "retention_days": 30}
        t = gen_siem.index_template(ds, "default", "siem.network-ilm")
        assert t["index_patterns"] == ["logs-siem.network-*"]
        assert t["data_stream"] == {}
        assert t["template"]["settings"]["index.lifecycle.name"] == "siem.network-ilm"
        assert t["template"]["settings"]["index.codec"] == "best_compression"

    def test_datasets_yaml_valid(self):
        cfg = yaml.safe_load((ROOT / "siem" / "datasets.yml").read_text())
        assert len(cfg["datasets"]) >= 4
        for d in cfg["datasets"]:
            assert d["name"].startswith("siem.") and d["retention_days"] > 0


class TestDataPipeline:
    LS = ROOT / "data-pipeline" / "logstash"
    FD = ROOT / "data-pipeline" / "fluentd"

    def test_no_malcolm_residue(self):
        # the pipeline is a universal ingest, not the Malcolm/OpenSearch stack
        for p in list(self.LS.rglob("*")) + list(self.FD.rglob("*")):
            if p.is_file() and p.suffix in {".conf", ".yml", ".yaml"} or p.name.startswith("Dockerfile"):
                text = p.read_text(errors="ignore").lower()
                for bad in ("opensearch", "malcolm", "zeek", "suricata", "netbox", "arkime"):
                    assert bad not in text, (p, bad)

    def test_logstash_compose_is_addon(self):
        doc = yaml.safe_load((self.LS / "docker-compose.yml").read_text())
        assert doc["networks"]["elastic"]["external"] is True
        assert doc["volumes"]["certs"]["external"] is True
        for s in doc["services"].values():
            assert not s.get("depends_on")           # foreign project
        raw = (self.LS / "docker-compose.yml").read_text()
        assert "config/certificates" not in raw      # healthcheck cacert path fixed
        assert "../.env" in raw

    def test_logstash_dockerfile_versioned(self):
        df = (self.LS / "Dockerfile").read_text()
        assert "ARG ELASTIC_VERSION" in df and "${ELASTIC_VERSION}" in df
        assert "logstash-oss:9.4.3" not in df

    def test_logstash_pipeline_tls_datastream(self):
        conf = (self.LS / "pipeline" / "logstash.conf").read_text()
        assert "https://elasticsearch:9200" in conf
        assert "ssl_certificate_authorities" in conf
        assert "data_stream => true" in conf
        assert "else [type]" not in conf             # invalid logstash; must be else if / conditional
        pl = (self.LS / "config" / "pipelines.yml").read_text()
        assert "main.conf" not in pl and "logstash.conf" in pl

    def test_logstash_examples_exist(self):
        ex = self.LS / "examples"
        names = {p.name for p in ex.glob("*.conf")}
        assert {"syslog-grok.conf", "nginx-access-geoip.conf", "json-app-dissect-dedup.conf"} <= names
        assert "grok" in (ex / "syslog-grok.conf").read_text()

    def test_fluentd_addon_tls(self):
        doc = yaml.safe_load((self.FD / "docker-compose.yml").read_text())
        assert doc["networks"]["elastic"]["external"] is True
        for s in doc["services"].values():
            assert "links" not in s                  # deprecated + foreign
            assert s["environment"]["FLUENT_ELASTICSEARCH_SCHEME"] == "https"
        conf = (self.FD / "conf" / "fluent.conf").read_text()
        assert "ca_file" in conf
        assert (self.FD / "examples" / "conf.d" / "syslog-grok.conf").exists()


class TestElasticsearchKafka:
    EK = ROOT / "elasticsearch-kafka"

    def test_kraft_no_zookeeper(self):
        doc = yaml.safe_load((self.EK / "docker-compose.yml").read_text())
        svc = doc["services"]
        assert "zookeeper" not in svc
        assert svc["kafka"]["environment"]["KAFKA_PROCESS_ROLES"] == "broker,controller"
        raw = (self.EK / "docker-compose.yml").read_text()
        assert ":latest" not in raw                    # images pinned
        assert "ELASTICSEARCH_URL" not in raw          # removed Kibana setting
        assert "${ELASTIC_VERSION" in raw              # version templated

    def test_connector_rest_payload(self):
        cfg = json.loads((self.EK / "kafka-connect" / "es-sink.json").read_text())
        assert cfg["config"]["connection.url"] == "http://elasticsearch:9200"
        assert not (self.EK / "kafka-connect" / "es.properties").exists()

    def test_es_client_current(self):
        req = (self.EK / "requirements.txt").read_text()
        assert "elasticsearch==7" not in req and "elasticsearch==9" in req


class TestK8s:
    def test_statefulset_pdb_and_kibana_hpa(self):
        docs = [d for d in yaml.safe_load_all(K8S) if d]
        kinds = [d["kind"] for d in docs]
        assert "StatefulSet" in kinds and "PodDisruptionBudget" in kinds
        hpa = [d for d in docs if d["kind"] == "HorizontalPodAutoscaler"][0]
        assert hpa["spec"]["scaleTargetRef"]["name"] == "kibana"

    def test_tls_versioned_no_hardcoded(self):
        assert "xpack.security.http.ssl.enabled" in K8S
        assert "${ELASTIC_VERSION}" in K8S     # image tags templated, not hardcoded
        assert "8.15.0" not in K8S             # stale otel version fixed


class TestAddonIntegration:
    ADDONS = ["apm-server", "beats/heart", "beats/metric", "beats/file", "curator", "fleet"]

    def _compose(self, addon):
        return yaml.safe_load((ROOT / addon / "docker-compose.yml").read_text())

    def test_external_network_and_certs(self):
        for a in self.ADDONS:
            doc = self._compose(a)
            net = doc["networks"]["elastic"]
            assert net["external"] is True and "elastic_elastic" in str(net["name"]), a
            vol = doc["volumes"]["certs"]
            assert vol["external"] is True and "elastic_certs" in str(vol["name"]), a

    def test_no_foreign_depends_on(self):
        # depends_on referencing services in the stack (different Compose project) is invalid
        for a in self.ADDONS:
            for sname, s in self._compose(a)["services"].items():
                assert not s.get("depends_on"), (a, sname)

    def test_certs_mounted_and_env_from_stack(self):
        for a in self.ADDONS:
            doc = self._compose(a)
            raw = (ROOT / a / "docker-compose.yml").read_text()
            mounted = any(
                isinstance(m, str) and m.startswith("certs:")
                for s in doc["services"].values() for m in s.get("volumes", [])
            )
            assert mounted, (a, "certs volume not mounted into any service")
            depth = "../../.env" if a.startswith("beats/") else "../.env"
            assert depth in raw, (a, "env_file must point at stack .env")

    def test_beats_and_apm_use_tls_ca(self):
        # every add-on config trusts the stack CA and talks https, not http
        checks = {
            "beats/metric/config/metricbeat.yml": "/certs/ca/ca.crt",
            "beats/file/config/filebeat.yml": "/certs/ca/ca.crt",
            "beats/heart/config/heartbeat.yml": "/certs/ca/ca.crt",
            "curator/config/curator.yml": "/certs/ca/ca.crt",
            "apm-server/conf/apm-server.yml": "ca/ca.crt",
        }
        for path, needle in checks.items():
            text = (ROOT / path).read_text()
            assert needle in text, path
        # metricbeat had http endpoints; the ES/Kibana/output ones must now be https
        mb = (ROOT / "beats/metric/config/metricbeat.yml").read_text()
        assert "http://elasticsearch:9200" not in mb and "http://kibana:5601" not in mb

    def test_enterprise_search_archived(self):
        assert not (ROOT / "enterprise-search").exists()          # discontinued in 9.x
        assert (ROOT / "archive" / "enterprise-search").exists()


class TestHostPrepAndSsh:
    def test_hostprep_has_revert_and_snapshot(self):
        assert "--revert" in HOSTPREP
        assert "vm.max_map_count" in HOSTPREP and "swappiness" in HOSTPREP

    def test_ssh_scripts(self):
        node = (ROOT / "ssh-deploy" / "node-up.sh").read_text()
        assert 'ROLE" = es' in node and 'ROLE" = kibana' in node
        assert (ROOT / "ssh-deploy" / "deploy-cluster.sh").exists()
        assert (ROOT / "ssh-deploy" / "cluster.hosts").exists()
