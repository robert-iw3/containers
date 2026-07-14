#!/usr/bin/env python3
"""
Render an OpenSearch docker-compose for any topology from a config file.

    python3 gen_opensearch.py [stack.config.yml] > docker-compose.generated.yml

The config drives node count (1-N), how many are cluster managers, dashboards
count, JVM heap (auto-sized from host RAM), TLS/security, and per-node memory
limits. Certificates for the rendered nodes come from certs/generate-certificates.sh.
"""
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_CONFIG = {
    "cluster_name": "opensearch-cluster",
    "opensearch": {"nodes": 3, "cluster_managers": 3, "heap": "auto"},
    "dashboards": {"nodes": 1},
    "security": True,
    "tls": True,
    "performance": {"memory_lock": True},
    "version": "3.2.0",
}

SECURITY_MOUNTS = [
    "audit.yml", "action_groups.yml", "config.yml", "internal_users.yml",
    "roles.yml", "roles_mapping.yml", "tenants.yml",
]


def total_ram_gb():
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return (pages * page_size) / (1024 ** 3)
    except (ValueError, OSError):
        return 8.0


def compute_heap(cfg, n_nodes):
    heap = cfg.get("opensearch", {}).get("heap", "auto")
    if heap != "auto":
        return heap
    per_node_gb = (total_ram_gb() * 0.5) / max(n_nodes, 1)
    gb = max(1, min(31, int(per_node_gb)))
    if per_node_gb < 1:
        return "512m"
    return f"{gb}g"


def mem_limit_for(heap):
    if heap.endswith("g"):
        return f"{int(heap[:-1]) * 2 * 1024}m"
    if heap.endswith("m"):
        return f"{int(heap[:-1]) * 2}m"
    return "2048m"


def node_names(n):
    return [f"opensearch-node{i}" for i in range(1, n + 1)]


def os_service(cfg, i, names, managers, heap, version, tls, security, memlock):
    name = names[i]
    is_manager = i < managers
    roles = "cluster_manager,data,ingest" if is_manager else "data,ingest"
    jvm = f"-Xms{heap} -Xmx{heap} -Xss256k -XX:-HeapDumpOnOutOfMemoryError " \
          "-Djava.security.egd=file:/dev/./urandom -Dlog4j.formatMsgNoLookups=true"
    env = {
        "cluster.name": cfg.get("cluster_name", "opensearch-cluster"),
        "node.name": name,
        "node.roles": roles,
        "discovery.seed_hosts": ",".join(names),
        "cluster.initial_cluster_manager_nodes": ",".join(names[:managers]),
        "bootstrap.memory_lock": "true" if memlock else "false",
        "OPENSEARCH_JAVA_OPTS": jvm,
        "DISABLE_INSTALL_DEMO_CONFIG": "true",
        "DISABLE_SECURITY_PLUGIN": "false" if security else "true",
        "logger.level": "WARN",
        "path.repo": "/opt/opensearch/backup",
    }
    volumes = [
        f"opensearch-data{i + 1}:/usr/share/opensearch/data",
        f"opensearch-backup{i + 1}:/opt/opensearch/backup",
        "./opensearch.yml:/usr/share/opensearch/config/opensearch.yml:ro",
    ]
    if tls:
        volumes += [
            "./certs/root-ca.pem:/usr/share/opensearch/config/root-ca.pem:ro",
            f"./certs/node{i + 1}.pem:/usr/share/opensearch/config/node.pem:ro",
            f"./certs/node{i + 1}-key.pem:/usr/share/opensearch/config/node-key.pem:ro",
            "./certs/admin.pem:/usr/share/opensearch/config/admin.pem:ro",
            "./certs/admin-key.pem:/usr/share/opensearch/config/admin-key.pem:ro",
        ]
    if security:
        volumes += [
            f"./security/{f}:/usr/share/opensearch/config/opensearch-security/{f}:ro"
            for f in SECURITY_MOUNTS
        ]
    svc = {
        "image": f"opensearchproject/opensearch:{version}",
        "build": {"context": ".", "dockerfile": "opensearch.Dockerfile"},
        "container_name": name,
        "hostname": name,
        "environment": env,
        "networks": ["opensearch"],
        "restart": "unless-stopped",
        "mem_limit": mem_limit_for(heap),
        "ulimits": {"memlock": {"soft": -1, "hard": -1}, "nofile": {"soft": 65535, "hard": 65535}},
        "cap_add": ["IPC_LOCK"],
        "volumes": volumes,
        "healthcheck": {
            "test": ["CMD-SHELL",
                     "curl -ksf https://localhost:9200/_cluster/health "
                     "-u \"admin:${OPENSEARCH_INITIAL_ADMIN_PASSWORD}\" >/dev/null || exit 1"],
            "interval": "20s", "timeout": "10s", "retries": 20, "start_period": "60s",
        },
    }
    if i == 0:
        svc["ports"] = ["9200:9200", "127.0.0.1:9600:9600"]
    return name, svc


def dashboards_service(idx, names, version, tls):
    name = "opensearch-dashboards" if idx == 0 else f"opensearch-dashboards{idx + 1}"
    volumes = ["./opensearch_dashboards.yml:/usr/share/opensearch-dashboards/config/opensearch_dashboards.yml:ro"]
    if tls:
        volumes += [
            "./certs/root-ca.pem:/usr/share/opensearch-dashboards/config/root-ca.pem:ro",
            "./certs/client.pem:/usr/share/opensearch-dashboards/config/client.pem:ro",
            "./certs/client-key.pem:/usr/share/opensearch-dashboards/config/client-key.pem:ro",
        ]
    hosts = "[" + ",".join(f'\"https://{n}:9200\"' for n in names) + "]"
    return name, {
        "image": f"opensearchproject/opensearch-dashboards:{version}",
        "build": {"context": ".", "dockerfile": "dashboards.Dockerfile"},
        "container_name": name,
        "environment": {"OPENSEARCH_HOSTS": hosts, "DISABLE_SECURITY_DASHBOARDS_PLUGIN": "false"},
        "networks": ["opensearch"],
        "restart": "unless-stopped",
        "ports": [f"{5601 + idx}:5601"],
        "volumes": volumes,
        "depends_on": {names[0]: {"condition": "service_healthy"}},
    }


def build(cfg):
    n = int(cfg.get("opensearch", {}).get("nodes", 3))
    managers = int(cfg.get("opensearch", {}).get("cluster_managers", min(3, n)))
    managers = max(1, min(managers, n))
    n_dash = int(cfg.get("dashboards", {}).get("nodes", 1))
    version = cfg.get("version", "3.2.0")
    tls = bool(cfg.get("tls", True))
    security = bool(cfg.get("security", True))
    memlock = bool(cfg.get("performance", {}).get("memory_lock", True))
    heap = compute_heap(cfg, n)

    names = node_names(n)
    services = {}
    for i in range(n):
        sname, svc = os_service(cfg, i, names, managers, heap, version, tls, security, memlock)
        services[sname] = svc
    for d in range(n_dash):
        dname, dsvc = dashboards_service(d, names, version, tls)
        services[dname] = dsvc

    volumes = {}
    for i in range(1, n + 1):
        volumes[f"opensearch-data{i}"] = None
        volumes[f"opensearch-backup{i}"] = None

    return {
        "services": services,
        "networks": {"opensearch": {"driver": "bridge"}},
        "volumes": volumes,
    }


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "stack.config.yml"
    cfg = dict(DEFAULT_CONFIG)
    if yaml and os.path.isfile(path):
        loaded = yaml.safe_load(open(path).read()) or {}
        cfg.update(loaded)
    compose = build(cfg)
    if yaml:
        print(yaml.safe_dump(compose, sort_keys=False, default_flow_style=False))
    else:
        print(compose)


if __name__ == "__main__":
    main()
