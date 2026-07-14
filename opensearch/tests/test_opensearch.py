"""Tests for the OpenSearch stack: Malcolm removal, the config-driven generator,
SIEM ISM policies/labeled indices, security wiring, and version pinning."""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "siem"))
import gen_opensearch  # noqa: E402
import gen_ism as gen_siem  # noqa: E402

COMPOSE = (ROOT / "docker-compose.yml").read_text()


def cfg(nodes=3, managers=3, dash=1, tls=True, security=True, heap="1g", memlock=True):
    return {
        "cluster_name": "opensearch-cluster", "version": "3.2.0",
        "opensearch": {"nodes": nodes, "cluster_managers": managers, "heap": heap},
        "dashboards": {"nodes": dash}, "tls": tls, "security": security,
        "performance": {"memory_lock": memlock},
    }


class TestMalcolmRemoved:
    def test_no_malcolm_anywhere(self):
        bad = ("malcolm", "zeek", "suricata", "netbox", "arkime")
        for p in ROOT.rglob("*"):
            if not p.is_file():
                continue
            if {"archive", ".eraser", "cdk", "tests"} & set(p.parts):
                continue
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".p12"}:
                continue
            text = p.read_text(errors="ignore").lower()
            for term in bad:
                assert term not in text, f"{p} still references {term}"

    def test_logstash_tree_gone(self):
        assert not (ROOT / "logstash").exists()


class TestGenerator:
    def test_topology_counts_and_roles(self):
        for n, m, d in [(1, 1, 1), (3, 3, 1), (5, 2, 2), (7, 3, 2)]:
            s = gen_opensearch.build(cfg(n, m, d))["services"]
            nodes = [k for k in s if k.startswith("opensearch-node")]
            dash = [k for k in s if k.startswith("opensearch-dashboards")]
            assert len(nodes) == n and len(dash) == d
            # first m nodes are cluster managers
            assert s["opensearch-node1"]["environment"]["node.roles"].startswith("cluster_manager")
            if n > m:
                assert s[f"opensearch-node{n}"]["environment"]["node.roles"] == "data,ingest"

    def test_auto_heap_and_mem_limit(self):
        assert gen_opensearch.compute_heap({"opensearch": {"heap": "auto"}}, 1000) == "512m"
        assert gen_opensearch.mem_limit_for("2g") == "4096m"
        s = gen_opensearch.build(cfg(heap="1g"))["services"]
        assert s["opensearch-node1"]["mem_limit"] == "2048m"
        assert "-Xms1g -Xmx1g" in s["opensearch-node1"]["environment"]["OPENSEARCH_JAVA_OPTS"]

    def test_tls_and_security_toggles(self):
        s = gen_opensearch.build(cfg(tls=True, security=True))["services"]["opensearch-node1"]
        assert any("node.pem" in v for v in s["volumes"])
        assert any("opensearch-security" in v for v in s["volumes"])
        assert s["environment"]["DISABLE_SECURITY_PLUGIN"] == "false"
        s2 = gen_opensearch.build(cfg(tls=False, security=False))["services"]["opensearch-node1"]
        assert not any("node.pem" in v for v in s2["volumes"])
        assert s2["environment"]["DISABLE_SECURITY_PLUGIN"] == "true"

    def test_healthcheck_and_memlock(self):
        s = gen_opensearch.build(cfg())["services"]["opensearch-node1"]
        assert "healthcheck" in s
        assert s["ulimits"]["memlock"]["soft"] == -1
        assert s["environment"]["bootstrap.memory_lock"] == "true"

    def test_renders_valid_yaml(self):
        doc = yaml.safe_load(yaml.safe_dump(gen_opensearch.build(cfg())))
        assert "services" in doc and "networks" in doc and "volumes" in doc


class TestSiemIsm:
    def test_ism_states_and_retention(self):
        pol = gen_siem.ism_policy({"name": "siem.auth", "retention_days": 90, "warm_after_days": 7})["policy"]
        assert [st["name"] for st in pol["states"]] == ["hot", "warm", "delete"]
        assert pol["states"][1]["transitions"][0]["conditions"]["min_index_age"] == "90d"
        assert pol["ism_template"][0]["index_patterns"] == ["logs-siem.auth-*"]
        assert "rollover" in pol["states"][0]["actions"][0]

    def test_labeled_data_stream_template(self):
        t = gen_siem.index_template({"name": "siem.network", "retention_days": 30}, "default")
        assert t["index_patterns"] == ["logs-siem.network-*"]
        assert t["data_stream"] == {}
        assert t["template"]["settings"]["index.codec"] == "best_compression"

    def test_datasets_valid(self):
        c = yaml.safe_load((ROOT / "siem" / "datasets.yml").read_text())
        assert len(c["datasets"]) >= 4
        for d in c["datasets"]:
            assert d["name"].startswith("siem.") and d["retention_days"] > 0


class TestK8s:
    K8S = ROOT / "opensearch-k8s.yaml"

    def test_pdb_hpa_and_pinned(self):
        docs = [d for d in yaml.safe_load_all(self.K8S.read_text()) if d]
        kinds = [d["kind"] for d in docs]
        assert "StatefulSet" in kinds and "PodDisruptionBudget" in kinds
        hpa = [d for d in docs if d["kind"] == "HorizontalPodAutoscaler"][0]
        assert hpa["spec"]["scaleTargetRef"]["name"] == "opensearch-dashboards"
        text = self.K8S.read_text()
        assert ":latest" not in text
        assert "opensearchproject/opensearch:3.2.0" in text


class TestDataPrepper:
    DP = ROOT / "data-prepper"

    def test_universal_pipeline_tls_labeled(self):
        text = (self.DP / "config" / "pipelines.yaml").read_text()
        p = yaml.safe_load(text)
        assert "log-pipeline" in p
        assert "http" in p["log-pipeline"]["source"]
        sink = p["log-pipeline"]["sink"][0]["opensearch"]
        assert sink["hosts"] == ["https://opensearch-node1:9200"]   # not localhost
        assert "root-ca.pem" in sink["cert"]
        assert sink["index"] == "logs-${dataset}-${namespace}"

    def test_addon_compose_external_network(self):
        doc = yaml.safe_load((self.DP / "docker-compose.yml").read_text())
        assert doc["networks"]["opensearch"]["external"] is True
        assert any("root-ca.pem" in v for v in doc["services"]["data-prepper"]["volumes"])


class TestDeployment:
    def test_host_prep_revert_and_sysctls(self):
        hp = (ROOT / "host-prep" / "prepare-host.sh").read_text()
        assert "--revert" in hp
        assert "vm.max_map_count" in hp and "memlock" in hp

    def test_ssh_and_ansible_present(self):
        assert (ROOT / "ssh-deploy" / "deploy-cluster.sh").exists()
        assert (ROOT / "ssh-deploy" / "cluster.hosts").exists()
        assert (ROOT / "ansible" / "deploy-opensearch.yml").exists()


class TestSecurityAndVersioning:
    def test_security_config_present(self):
        # compose mounts security/config.yml; it must exist (not just .example)
        for f in ["audit", "action_groups", "config", "internal_users", "roles", "roles_mapping", "tenants"]:
            assert (ROOT / "security" / f"{f}.yml").is_file(), f

    def test_admin_dn_not_placeholder(self):
        osyml = (ROOT / "opensearch.yml").read_text()
        assert "CN=admin," in osyml           # real admin DN, not the empty CN= placeholder
        assert "CN=,OU=,O=" not in osyml

    def test_images_pinned(self):
        assert ":latest" not in COMPOSE
        assert "${OPENSEARCH_VERSION" in COMPOSE

    def test_env_example_present(self):
        env = (ROOT / ".env.example").read_text()
        assert "OPENSEARCH_INITIAL_ADMIN_PASSWORD" in env
