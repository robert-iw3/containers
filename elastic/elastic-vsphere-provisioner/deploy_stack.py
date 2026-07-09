#!/usr/bin/env python3
"""
Deploys Elastic Stack via Ansible + Full Validation
Generates dynamic ES hosts list from inventory
"""
import os
import sys
import time
import json
import requests
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import ast

load_dotenv()
BASE = Path(__file__).parent

# === CONFIG FROM .env ===
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD")
KIBANA_PASSWORD = os.getenv("KIBANA_SYSTEM_PASSWORD")
VM_SPECS = ast.literal_eval(os.getenv("VM_SPECS", "{}"))
ALLOWED_SUBNET = os.getenv("ALLOWED_SUBNET", "192.168.1.0/24")
CONTAINER_RUNTIME = os.getenv("CONTAINER_RUNTIME", "podman")

def choose_runtime():
    print("Choose container runtime:")
    print("  1. Docker")
    print("  2. Podman")
    while True:
        choice = input("Enter (1/2): ").strip()
        if choice == "1":
            return "docker"
        elif choice == "2":
            return "podman"
        print("Invalid choice.")

def generate_inventory():
    """Generate dynamic inventory from VM_SPECS"""
    inventory = BASE / "inventory" / "hosts.ini"
    inventory.parent.mkdir(exist_ok=True)

    with open(inventory, "w") as f:
        # Elasticsearch group
        f.write("[elasticsearch]\n")
        for name, spec in VM_SPECS.items():
            if "es-node" in name:
                f.write(f"{name} ansible_host={spec['ip']} ansible_user={os.getenv('SSH_USER')}\n")
        f.write("\n")

        # Kibana group
        f.write("[kibana]\n")
        for name, spec in VM_SPECS.items():
            if "kibana" in name:
                f.write(f"{name} ansible_host={spec['ip']} ansible_user={os.getenv('SSH_USER')}\n")
        f.write("\n")

        # Global vars
        f.write("[all:vars]\n")
        f.write(f"ansible_ssh_private_key_file={os.getenv('SSH_KEY')}\n")
        f.write(f"allowed_subnet={ALLOWED_SUBNET}\n")
        f.write(f"container_runtime={CONTAINER_RUNTIME}\n")

    print(f"Inventory generated: {inventory}")
    return str(inventory)

def generate_es_hosts_list():
    """Generate ES hosts list for Kibana"""
    es_hosts = []
    for name, spec in VM_SPECS.items():
        if "es-node" in name:
            es_hosts.append(f"https://{spec['ip']}:9200")
    return json.dumps(es_hosts)

def wait_for_es():
    print("Waiting for Elasticsearch cluster...")
    auth = ("elastic", ELASTIC_PASSWORD)
    es_ip = next((spec["ip"] for spec in VM_SPECS.values() if "es-node" in spec), None)
    if not es_ip:
        print("No ES node found!")
        return False

    for _ in range(30):
        try:
            r = requests.get(f"https://{es_ip}:9200/_cluster/health", auth=auth, verify=False, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data["status"] in ["yellow", "green"] and data["number_of_nodes"] >= 3:
                    print(f"CLUSTER HEALTHY: {data['status']} ({data['number_of_nodes']} nodes)")
                    return True
        except Exception as e:
            print(f"ES check failed: {e}")
            time.sleep(10)
    return False

def check_kibana():
    print("Checking Kibana...")
    kibana_ip = next((spec["ip"] for spec in VM_SPECS.values() if "kibana" in spec), None)
    if not kibana_ip:
        print("No Kibana node found!")
        return False

    for _ in range(20):
        try:
            r = requests.get(f"https://{kibana_ip}:5601/api/status", auth=("kibana_system", KIBANA_PASSWORD), verify=False, timeout=10)
            if r.status_code == 200 and "kibana" in r.text.lower():
                print("Kibana OK")
                return True
        except Exception as e:
            print(f"Kibana check failed: {e}")
            time.sleep(10)
    return False

def check_fleet():
    print("Checking Fleet Server...")
    fleet_ip = next((spec["ip"] for spec in VM_SPECS.values() if "kibana" in spec), None)
    if not fleet_ip:
        print("No Fleet node found!")
        return False

    for _ in range(15):
        try:
            r = requests.get(f"https://{fleet_ip}:8220/api/status", verify=False, timeout=10)
            if r.status_code == 200:
                print("Fleet Server OK")
                return True
        except Exception as e:
            print(f"Fleet check failed: {e}")
            time.sleep(10)
    return False

def deploy_and_validate_stack():
    # Choose runtime (if not in .env)
    global CONTAINER_RUNTIME
    if not CONTAINER_RUNTIME:
        CONTAINER_RUNTIME = choose_runtime()

    # Generate inventory
    inventory_path = generate_inventory()

    # Generate ES hosts list
    es_hosts_list = generate_es_hosts_list()

    # Extra vars
    extra_vars = {
        "elastic_password": ELASTIC_PASSWORD,
        "kibana_password": KIBANA_PASSWORD,
        "container_runtime": CONTAINER_RUNTIME,
        "allowed_subnet": ALLOWED_SUBNET,
        "es_hosts_list": es_hosts_list
    }

    print(f"Deploying with {CONTAINER_RUNTIME.upper()}...")
    try:
        subprocess.run([
            "ansible-playbook",
            "-i", inventory_path,
            str(BASE / "playbook.yml"),
            "--extra-vars", json.dumps(extra_vars)
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ansible failed: {e}")
        sys.exit(1)

    # Full validation
    if not wait_for_es():
        print("Elasticsearch cluster failed")
        sys.exit(1)
    if not check_kibana():
        print("Kibana failed")
        sys.exit(1)
    if not check_fleet():
        print("Fleet Server failed")
        sys.exit(1)

    print("FULL STACK DEPLOYED AND VALIDATED!")

if __name__ == "__main__":
    deploy_and_validate_stack()