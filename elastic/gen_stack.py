#!/usr/bin/env python3
"""Render a configurable Elastic SIEM docker-compose from stack.config.yml.

One config drives any topology -- scale Elasticsearch 1..7, run 1..2 Kibana search
heads, toggle Fleet Server / Logstash, TLS on/off. The generated `setup` service
mints a CA + per-node certs for exactly the instances it renders, so TLS is correct
at any size.

    python3 gen_stack.py [stack.config.yml] > docker-compose.generated.yml

Only PyYAML is needed.
"""

from __future__ import annotations

import sys

import yaml

ES = "elasticsearch"


def total_ram_gb() -> float:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024 / 1024
    except OSError:
        pass
    return 8.0


def compute_heap(cfg: dict, n_nodes: int) -> str:
    """Optimal JVM heap from discovered RAM: 50% of host RAM split across the nodes
    on this host, capped at 31g (compressed-oops threshold), floored at 512m."""
    h = cfg["elasticsearch"].get("heap", "auto")
    if h != "auto":
        return h
    per = (total_ram_gb() * 0.5) / max(1, n_nodes)
    g = max(0.5, min(31.0, round(per * 2) / 2))   # round to 0.5g
    return f"{int(g)}g" if g == int(g) else f"{int(g * 1024)}m"


def mem_limit_for(heap: str) -> str:
    # Container limit ~= 2x heap (heap + off-heap/direct/page cache headroom).
    n = float(heap[:-1])
    unit = heap[-1]
    mb = n * 1024 if unit == "g" else n
    return f"{int(mb * 2)}m"


def es_name(i: int) -> str:
    return f"es{i:02d}"


def kib_name(i: int) -> str:
    return f"kibana{i:02d}"


def instances(cfg: dict) -> list[str]:
    names = [es_name(i) for i in range(1, cfg["elasticsearch"]["nodes"] + 1)]
    names += [kib_name(i) for i in range(1, cfg["kibana"]["nodes"] + 1)]
    if cfg.get("fleet"):
        names.append("fleet-server")
    return names


def instances_yaml(names: list[str]) -> str:
    # A single flow-style string for the instances.yml that certutil consumes.
    # Flow style ([a, b]) sidesteps block-sequence indentation, and one printf arg
    # avoids echo's arg-join spaces corrupting the indentation.
    s = "instances:\\n"
    for n in names:
        s += f"  - name: {n}\\n    dns: [{n}, localhost]\\n    ip: [127.0.0.1]\\n"
    return s


def setup_service(cfg: dict, names: list[str]) -> dict:
    inst = instances_yaml(names)
    cmd = f"""bash -c '
  if [ x${{ELASTIC_PASSWORD}} == x ]; then echo "Set ELASTIC_PASSWORD in .env"; exit 1; fi;
  if [ ! -f config/certs/ca.zip ]; then
    bin/elasticsearch-certutil ca --silent --pem -out config/certs/ca.zip;
    unzip config/certs/ca.zip -d config/certs;
  fi;
  if [ ! -f config/certs/certs.zip ]; then
    printf "%b" "{inst}" > config/certs/instances.yml;
    bin/elasticsearch-certutil cert --silent --pem -out config/certs/certs.zip --in config/certs/instances.yml --ca-cert config/certs/ca/ca.crt --ca-key config/certs/ca/ca.key;
    unzip config/certs/certs.zip -d config/certs;
    for n in {" ".join(names)}; do cat config/certs/$$n/$$n.crt config/certs/ca/ca.crt > config/certs/$$n/$$n.chain.pem; done;
  fi;
  chown -R root:root config/certs;
  find . -type d -exec chmod 750 \\{{\\}} \\;;
  find . -type f -exec chmod 640 \\{{\\}} \\;;
  until curl -s --cacert config/certs/ca/ca.crt https://{es_name(1)}:9200 | grep -q "missing authentication credentials"; do sleep 5; done;
  until curl -s -X POST --cacert config/certs/ca/ca.crt -u elastic:${{ELASTIC_PASSWORD}} -H "Content-Type: application/json" https://{es_name(1)}:9200/_security/user/kibana_system/_password -d "{{\\"password\\":\\"${{KIBANA_SYSTEM_PASSWORD}}\\"}}" | grep -q "^{{}}"; do sleep 5; done;
  echo "setup done";
'"""
    return {
        "image": "docker.elastic.co/elasticsearch/elasticsearch:${ELASTIC_VERSION}",
        "container_name": "elastic-setup",
        "init": True,
        "user": "0",
        "networks": ["elastic"],
        "volumes": ["certs:/usr/share/elasticsearch/config/certs:z"],
        "environment": {
            "ELASTIC_PASSWORD": "${ELASTIC_PASSWORD}",
            "KIBANA_SYSTEM_PASSWORD": "${KIBANA_SYSTEM_PASSWORD}",
        },
        "command": cmd,
        "healthcheck": {
            "test": ["CMD-SHELL", f"[ -f config/certs/{es_name(1)}/{es_name(1)}.crt ]"],
            "interval": "2s", "timeout": "5s", "retries": 120,
        },
    }


def es_service(cfg: dict, i: int, all_es: list[str], heap: str) -> dict:
    name = es_name(i)
    tls = cfg.get("tls", True)
    perf = cfg.get("performance", {})
    env = {
        "node.name": name,
        "cluster.name": cfg["cluster_name"],
        "cluster.initial_master_nodes": ",".join(all_es),
        "discovery.seed_hosts": ",".join(n for n in all_es if n != name) or name,
        # memory_lock pins the heap (production: true + host memlock=unlimited via
        # host-prep). Toggle off where the host memlock limit can't be raised.
        "bootstrap.memory_lock": "true" if perf.get("memory_lock", True) else "false",
        "ELASTIC_PASSWORD": "${ELASTIC_PASSWORD}",
        "ES_JAVA_OPTS": f"-Xms{heap} -Xmx{heap}",
        "xpack.security.enabled": "true",
        "xpack.license.self_generated.type": "trial",
        "xpack.security.authc.api_key.enabled": "true",
    }
    if tls:
        env.update({
            "xpack.security.http.ssl.enabled": "true",
            "xpack.security.http.ssl.key": f"certs/{name}/{name}.key",
            "xpack.security.http.ssl.certificate": f"certs/{name}/{name}.chain.pem",
            "xpack.security.http.ssl.certificate_authorities": "certs/ca/ca.crt",
            "xpack.security.transport.ssl.enabled": "true",
            "xpack.security.transport.ssl.key": f"certs/{name}/{name}.key",
            "xpack.security.transport.ssl.certificate": f"certs/{name}/{name}.crt",
            "xpack.security.transport.ssl.certificate_authorities": "certs/ca/ca.crt",
            "xpack.security.transport.ssl.verification_mode": "certificate",
        })
    scheme = "https" if tls else "http"
    cacert = "--cacert config/certs/ca/ca.crt " if tls else ""
    svc = {
        "image": "docker.elastic.co/elasticsearch/elasticsearch:${ELASTIC_VERSION}",
        "container_name": f"elastic-{name}",
        "hostname": name,
        "depends_on": {"setup": {"condition": "service_healthy"}},
        "ulimits": {"memlock": {"soft": -1, "hard": -1}},
        "networks": ["elastic"],
        "restart": "unless-stopped",
        "mem_limit": mem_limit_for(heap),
        "volumes": [f"{name}:/usr/share/elasticsearch/data:Z", "certs:/usr/share/elasticsearch/config/certs:z"],
        "environment": env,
        "healthcheck": {
            "test": ["CMD-SHELL", f"curl -s {cacert}{scheme}://localhost:9200 | grep -q 'missing authentication credentials'"],
            "interval": "10s", "timeout": "10s", "retries": 120,
        },
    }
    if i == 1:
        svc["ports"] = ["9200:9200"]
    return svc


def kibana_service(cfg: dict, i: int, all_es: list[str]) -> dict:
    name = kib_name(i)
    tls = cfg.get("tls", True)
    scheme = "https" if tls else "http"
    env = {
        "SERVER_NAME": name,
        "ELASTICSEARCH_HOSTS": "[" + ",".join(f'"{scheme}://{e}:9200"' for e in all_es) + "]",
        "ELASTICSEARCH_USERNAME": "kibana_system",
        "ELASTICSEARCH_PASSWORD": "${KIBANA_SYSTEM_PASSWORD}",
    }
    if tls:
        env.update({
            "ELASTICSEARCH_SSL_CERTIFICATEAUTHORITIES": "config/certs/ca/ca.crt",
            "SERVER_SSL_ENABLED": "true",
            "SERVER_SSL_CERTIFICATE": f"config/certs/{name}/{name}.crt",
            "SERVER_SSL_KEY": f"config/certs/{name}/{name}.key",
        })
    return {
        "image": "docker.elastic.co/kibana/kibana:${ELASTIC_VERSION}",
        "container_name": name,
        "depends_on": {es_name(1): {"condition": "service_healthy"}},
        "networks": ["elastic"],
        "restart": "unless-stopped",
        "volumes": [f"{name}:/usr/share/kibana/data:Z", "certs:/usr/share/kibana/config/certs:z"],
        "ports": [f"{5601 + i - 1}:5601"],
        "environment": env,
    }


def build(cfg: dict) -> dict:
    n_es = cfg["elasticsearch"]["nodes"]
    all_es = [es_name(i) for i in range(1, n_es + 1)]
    names = instances(cfg)
    heap = compute_heap(cfg, n_es)
    services = {"setup": setup_service(cfg, names)}
    for i in range(1, n_es + 1):
        services[es_name(i)] = es_service(cfg, i, all_es, heap)
    for i in range(1, cfg["kibana"]["nodes"] + 1):
        services[kib_name(i)] = kibana_service(cfg, i, all_es)
    if cfg.get("fleet"):
        services["fleet-server"] = {
            "image": "docker.elastic.co/elastic-agent/elastic-agent:${ELASTIC_VERSION}",
            "container_name": "fleet-server",
            "hostname": "fleet-server",
            "depends_on": {kib_name(1): {"condition": "service_started"}, es_name(1): {"condition": "service_healthy"}},
            "networks": ["elastic"],
            "user": "root",
            "ports": ["8220:8220"],
            "volumes": ["certs:/certs:z", "fleetserver:/usr/share/elastic-agent:Z"],
            "environment": {
                "FLEET_SERVER_ENABLE": "1", "FLEET_ENROLL": "1", "KIBANA_FLEET_SETUP": "1",
                "FLEET_SERVER_POLICY_ID": "fleet-server-policy",
                "KIBANA_HOST": f"https://{kib_name(1)}:5601",
                "FLEET_URL": "https://fleet-server:8220",
                "FLEET_SERVER_ELASTICSEARCH_HOST": f"https://{es_name(1)}:9200",
                "FLEET_CA": "/certs/ca/ca.crt", "FLEET_SERVER_ELASTICSEARCH_CA": "/certs/ca/ca.crt",
                "KIBANA_FLEET_CA": "/certs/ca/ca.crt",
                "KIBANA_FLEET_USERNAME": "elastic", "KIBANA_FLEET_PASSWORD": "${ELASTIC_PASSWORD}",
                "FLEET_SERVER_CERT": "/certs/fleet-server/fleet-server.crt",
                "FLEET_SERVER_CERT_KEY": "/certs/fleet-server/fleet-server.key",
            },
        }
    if cfg.get("logstash"):
        services["logstash"] = {
            "image": "docker.elastic.co/logstash/logstash:${ELASTIC_VERSION}",
            "container_name": "logstash",
            "depends_on": {es_name(1): {"condition": "service_healthy"}},
            "networks": ["elastic"], "restart": "unless-stopped",
            "volumes": ["certs:/certs:z", "./data-pipeline/logstash/pipeline:/usr/share/logstash/pipeline:ro"],
            "environment": {"LS_JAVA_OPTS": "-Xms512m -Xmx512m"},
        }
    volumes = {"certs": None, "fleetserver": None}
    for i in range(1, n_es + 1):
        volumes[es_name(i)] = None
    for i in range(1, cfg["kibana"]["nodes"] + 1):
        volumes[kib_name(i)] = None
    return {
        "services": services,
        "networks": {"elastic": {"driver": "bridge"}},
        "volumes": volumes,
    }


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "stack.config.yml"
    cfg = yaml.safe_load(open(path))
    n = cfg["elasticsearch"]["nodes"]
    if not 1 <= n <= 7:
        sys.exit("elasticsearch.nodes must be 1-7")
    if not 1 <= cfg["kibana"]["nodes"] <= 2:
        sys.exit("kibana.nodes must be 1-2")
    header = (
        f"# GENERATED by gen_stack.py from {path} -- edit that, not this file.\n"
        f"# topology: {n} elasticsearch, {cfg['kibana']['nodes']} kibana, "
        f"fleet={bool(cfg.get('fleet'))}, logstash={bool(cfg.get('logstash'))}, tls={cfg.get('tls', True)}\n"
    )
    sys.stdout.write(header + yaml.safe_dump(build(cfg), sort_keys=False, width=1000))


if __name__ == "__main__":
    main()
