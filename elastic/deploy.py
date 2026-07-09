#!/usr/bin/env python3
"""
Elastic Stack Orchestrator
Supports: Docker, Podman, Kubernetes, Ansible
Version: Read from .env (ELASTIC_VERSION)
Interactive mode + .env override
"""
import os
import sys
import time
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
BASE = Path(__file__).parent

# Read ELASTIC_VERSION from .env (required)
ELASTIC_VERSION = os.getenv("ELASTIC_VERSION")
if not ELASTIC_VERSION:
    print("ERROR: ELASTIC_VERSION is required in .env")
    print("Example: ELASTIC_VERSION=9.2.0")
    sys.exit(1)

# Optional: DEPLOY_TARGET (interactive if missing)
TARGET = os.getenv("DEPLOY_TARGET", "").lower()
VALID_TARGETS = ["docker", "podman", "k8s", "ansible"]

def run(cmd, **kwargs):
    print(f"[RUN] {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, shell=isinstance(cmd, str), check=True, capture_output=True, **kwargs)
    return result.stdout.decode()

def generate_certs():
    print(f"Generating TLS certificates for Elastic {ELASTIC_VERSION}...")
    certs_dir = BASE / "certs"
    certs_dir.mkdir(exist_ok=True)
    if (certs_dir / "ca" / "ca.crt").exists():
        print("Certs already exist.")
        return
    run([
        "docker", "run", "--rm",
        "-v", f"{certs_dir}:/certs",
        f"docker.elastic.co/elasticsearch/elasticsearch:{ELASTIC_VERSION}",
        "bash", "-c",
        """
        set -e
        bin/elasticsearch-certutil ca --silent --pem --out /certs/ca.zip
        unzip -o /certs/ca.zip -d /certs/ca
        cat > /certs/instances.yml <<'EOF'
instances:
  - name: elasticsearch
    dns: [elasticsearch, localhost]
    ip: [127.0.0.1]
  - name: elasticsearch1
    dns: [elasticsearch1, localhost]
    ip: [127.0.0.1]
  - name: elasticsearch2
    dns: [elasticsearch2, localhost]
    ip: [127.0.0.1]
  - name: kibana
    dns: [kibana, localhost, kibana.elastic.local]
    ip: [127.0.0.1]
  - name: fleet-server
    dns: [fleet-server, localhost, fleet.elastic.local]
    ip: [127.0.0.1]
EOF
        bin/elasticsearch-certutil cert --silent --pem \
          --ca-cert /certs/ca/ca.crt --ca-key /certs/ca/ca.key \
          --in /certs/instances.yml --out /certs/certs.zip
        unzip -o /certs/certs.zip -d /certs
        for i in elasticsearch elasticsearch1 elasticsearch2; do
          cat /certs/$i/$i.crt /certs/ca/ca.crt > /certs/$i/$i.chain.pem
        done
        chown -R 1000:1000 /certs
        """
    ])

def seal_secrets():
    print("Sealing Kubernetes secrets...")
    sealed_dir = BASE / "kubernetes" / "sealed"
    sealed_dir.mkdir(parents=True, exist_ok=True)
    run(f"bash {BASE}/seal-secret.sh")

def deploy_docker():
    generate_certs()
    run(["docker", "compose", "-f", str(BASE / "docker-compose-multi-node.yml"), "up", "-d"])

def deploy_podman():
    generate_certs()
    run(["podman-compose", "-f", str(BASE / "docker-compose-multi-node.yml"), "up", "-d"])

def deploy_k8s():
    generate_certs()
    seal_secrets()
    run(["kubectl", "apply", "-f", str(BASE / "kubernetes" / "rbac.yaml")])
    run(["kubectl", "apply", "-f", str(BASE / "kubernetes" / "networkpolicy.yaml")])
    run(["kubectl", "apply", "-f", str(BASE / "kubernetes" / "elastic-k8s.yml")])
    run(["kubectl", "apply", "-f", str(BASE / "kubernetes" / "ingress.yaml")])
    print("Waiting for Ingress...")
    time.sleep(60)

def deploy_ansible():
    print("Deploying via Ansible...")
    generate_certs()
    seal_secrets()
    target = input("Choose Ansible target (docker/podman/k8s): ").strip().lower()
    if target not in ["docker", "podman", "k8s"]:
        print("Invalid target. Use docker, podman, or k8s.")
        sys.exit(1)
    inventory = f"ansible/inventory/{target}.ini"
    playbook = "ansible/playbook.yml"
    run([
        "ansible-playbook",
        "-i", inventory,
        playbook,
        "--extra-vars", f"target={target}"
    ])

def smoke_test():
    print("Running smoke tests...")
    auth = ("elastic", os.getenv("ELASTIC_PASSWORD"))
    urls = {
        "Kibana": "https://kibana.elastic.local/api/status",
        "Fleet": "https://fleet.elastic.local",
    }
    for name, url in urls.items():
        for _ in range(30):
            try:
                r = requests.get(url, auth=auth if "kibana" in url.lower() else None, verify=False, timeout=10)
                if r.status_code < 400:
                    print(f"{name} OK")
                    break
            except:
                time.sleep(10)
        else:
            print(f"{name} FAILED")
            sys.exit(1)
    print("ALL TESTS PASSED!")

def interactive_mode():
    print("Elastic Stack Deployment Orchestrator")
    print(f"Version: {ELASTIC_VERSION}")
    print("Available methods: docker, podman, k8s, ansible")
    while True:
        choice = input("Choose deployment method (docker/podman/k8s/ansible): ").strip().lower()
        if choice in VALID_TARGETS:
            return choice
        print("Invalid choice. Try again.")

if __name__ == "__main__":
    # CLI flags
    if "--generate-certs" in sys.argv:
        generate_certs()
        sys.exit(0)
    if "--cleanup" in sys.argv:
        target = TARGET or "docker"
        if target == "k8s":
            run(["kubectl", "delete", "namespace", "elastic", "--grace-period=0", "--force"], stderr=subprocess.DEVNULL)
        elif target in ["docker", "podman"]:
            run([target, "compose", "-f", str(BASE / "docker-compose-multi-node.yml"), "down", "-v"])
        elif target == "ansible":
            print("Cleanup via Ansible not automated. Run manually.")
        sys.exit(0)

    # Determine target
    target = TARGET
    if not target:
        target = interactive_mode()
    elif target not in VALID_TARGETS:
        print(f"Invalid DEPLOY_TARGET: {target}. Use: {', '.join(VALID_TARGETS)}")
        sys.exit(1)

    print(f"Deploying via {target.upper()} (Elastic {ELASTIC_VERSION})")

    # Route to deployment method
    if target == "docker":
        deploy_docker()
    elif target == "podman":
        deploy_podman()
    elif target == "k8s":
        deploy_k8s()
    elif target == "ansible":
        deploy_ansible()

    # Final check
    smoke_test()
    print(f"Deployment complete! Kibana: https://kibana.elastic.local")