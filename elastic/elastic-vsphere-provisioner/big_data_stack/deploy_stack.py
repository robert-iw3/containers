#!/usr/bin/env python3
"""
Deploys Big Data Stack via Ansible
"""
import os
import sys
import time
import json
import requests
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE = Path(__file__).parent

VM_SPECS = json.loads(os.getenv("VM_SPECS", "{}"))
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD")
KIBANA_PASSWORD = os.getenv("KIBANA_SYSTEM_PASSWORD")

def deploy_and_validate_stack():
    inventory_path = BASE / "inventory" / "hosts.ini"
    inventory_path.parent.mkdir(exist_ok=True)

    with open(inventory_path, "w") as f:
        f.write("[master]\n")
        for name, spec in VM_SPECS.items():
            if spec.get("role") == "master":
                f.write(f"{name} ansible_host={spec['ip']}\n")

        f.write("\n[data_hot]\n")
        for name, spec in VM_SPECS.items():
            if spec.get("role") == "data_hot":
                f.write(f"{name} ansible_host={spec['ip']}\n")

        f.write("\n[data_warm]\n")
        for name, spec in VM_SPECS.items():
            if spec.get("role") == "data_warm":
                f.write(f"{name} ansible_host={spec['ip']}\n")

        f.write("\n[coordinating]\n")
        for name, spec in VM_SPECS.items():
            if spec.get("role") == "coordinating":
                f.write(f"{name} ansible_host={spec['ip']}\n")

        f.write("\n[kibana]\n")
        for name, spec in VM_SPECS.items():
            if spec.get("role") == "kibana":
                f.write(f"{name} ansible_host={spec['ip']}\n")

        f.write("\n[fleet]\n")
        for name, spec in VM_SPECS.items():
            if spec.get("role") == "fleet":
                f.write(f"{name} ansible_host={spec['ip']}\n")

        f.write("\n[lb]\n")
        for name, spec in VM_SPECS.items():
            if spec.get("role") == "lb":
                f.write(f"{name} ansible_host={spec['ip']}\n")

        f.write("\n[all:vars]\n")
        f.write(f"ansible_ssh_private_key_file={os.getenv('SSH_KEY')}\n")
        f.write(f"allowed_subnet={os.getenv('SUBNET')}\n")
        f.write(f"container_runtime={os.getenv('CONTAINER_RUNTIME')}\n")

    extra_vars = {
        "elastic_password": ELASTIC_PASSWORD,
        "kibana_password": KIBANA_PASSWORD,
    }

    print("Deploying stack...")
    subprocess.run([
        "ansible-playbook",
        "-i", str(inventory_path),
        str(BASE / "playbook.yml"),
        "--extra-vars", json.dumps(extra_vars)
    ], check=True)

    print("STACK DEPLOYED!")

if __name__ == "__main__":
    deploy_and_validate_stack()