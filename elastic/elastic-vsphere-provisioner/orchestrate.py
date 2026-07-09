#!/usr/bin/env python3
"""
Elastic vSphere Full Automation Orchestrator
=========================================
ALL CONFIGURABLE: IPs, hostnames, VM specs, distro, Docker/Podman, passwords
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Local imports
from provision_vms import provision_and_validate_vms
from deploy_stack import deploy_and_validate_stack

load_dotenv()
BASE = Path(__file__).parent
POWERSHELL_SCRIPT = BASE / "install_powercli.ps1"
DISTROS = ["ubuntu", "debian", "almalinux", "rhel"]


# ----------------------------------------------------------------------
# Helper functions (PowerShell, PowerCLI, prompts, etc.)
# ----------------------------------------------------------------------
def run_powershell(script: str) -> str:
    try:
        result = subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"PowerShell Error: {e.stderr}")
        sys.exit(1)


def check_powercli() -> bool:
    script = "if (Get-Module -ListAvailable -Name VMware.PowerCLI) { 'INSTALLED' } else { 'MISSING' }"
    return run_powershell(script).strip() == "INSTALLED"


def install_powercli() -> None:
    if check_powercli():
        print("PowerCLI already installed.")
        return
    print("Installing PowerCLI...")
    if not POWERSHELL_SCRIPT.exists():
        print(f"ERROR: {POWERSHELL_SCRIPT} missing!")
        sys.exit(1)
    output = run_powershell(f"Get-Content '{POWERSHELL_SCRIPT}' -Raw | Invoke-Expression")
    print(output)


# ----------------------------------------------------------------------
# Prompt helpers
# ----------------------------------------------------------------------
def prompt_vsphere() -> dict:
    print("\n=== vSPHERE CONFIGURATION ===")
    return {
        "vcenter_host": input("vCenter Host: ").strip() or "vcenter.example.com",
        "vcenter_user": input("vCenter User: ").strip() or "admin@vsphere.local",
        "vcenter_password": input("vCenter Password: ").strip(),
        "datacenter": input("Datacenter: ").strip() or "Datacenter",
        "cluster": input("Cluster: ").strip() or "Cluster",
        "datastore": input("Datastore: ").strip() or "datastore1",
        "template": input("VM Template: ").strip() or "ubuntu-template"
    }


def prompt_cloudinit() -> dict:
    print("\n=== CLOUD-INIT CONFIGURATION ===")
    cfg = {
        "ssh_user": input("SSH Username [elastic]: ").strip() or "elastic",
        "ssh_password": input("SSH Password (Enter for random): ").strip(),
        "nameservers": input("DNS Nameservers [8.8.8.8,1.1.1.1]: ").strip() or "8.8.8.8,1.1.1.1",
        "gateway": input("Gateway IP [192.168.1.1]: ").strip() or "192.168.1.1",
        "timezone": input("Timezone [UTC]: ").strip() or "UTC",
        "packages": input("Extra Packages [vim,curl,git]: ").strip() or "vim,curl,git"
    }
    if not cfg["ssh_password"]:
        cfg["ssh_password"] = subprocess.getoutput("openssl rand -hex 16")
        print(f"Generated SSH password: {cfg['ssh_password']}")
    return cfg


def prompt_vm_specs() -> dict:
    """
    Returns:
        {
            "my-es-01": {"cpu": 4, "ram_gb": 16, "disk_gb": 100, "ip": "10.0.0.11", "hostname": "my-es-01"},
            ...
        }
    """
    print("\n=== VM SPEC CONFIGURATION ===")
    vm_specs = {}
    raw = input(
        "VM Names (comma-separated) [es-node1,es-node2,es-node3,kibana-vm1,kibana-vm2,fleet-server1]: "
    ).strip()
    vm_names = [n.strip() for n in raw.split(",")] if raw else [
        "es-node1", "es-node2", "es-node3", "kibana-vm1", "kibana-vm2", "fleet-server1"
    ]

    for vm_name in vm_names:
        print(f"\nConfiguring {vm_name}:")
        cpu = int(input(" CPU Cores [4]: ") or "4")
        ram_gb = int(input(" RAM (GB) [16]: ") or "16")
        disk_gb = int(input(" Disk (GB) [100]: ") or "100")
        ip = input(" IP Address: ").strip()
        if not ip:
            print("IP required!")
            sys.exit(1)
        hostname = input(f" Hostname [{vm_name}]: ").strip() or vm_name
        vm_specs[vm_name] = {
            "cpu": cpu,
            "ram_gb": ram_gb,
            "disk_gb": disk_gb,
            "ip": ip,
            "hostname": hostname
        }
    return vm_specs


def prompt_security() -> dict:
    print("\n=== SECURITY CONFIGURATION ===")
    subnet = input("Allowed Subnet (e.g. 192.168.1.0/24): ").strip()
    if not subnet:
        print("Subnet required for security!")
        sys.exit(1)
    return {"allowed_subnet": subnet}


def choose_distro() -> str:
    print("\nChoose Linux Distro:")
    for i, d in enumerate(DISTROS, 1):
        print(f" {i}. {d.capitalize()}")
    while True:
        c = input("Enter (1-4): ").strip()
        if c in ["1", "2", "3", "4"]:
            distro = DISTROS[int(c) - 1]
            os.environ["DISTRO"] = distro
            print(f"Selected: {distro.upper()}")
            return distro
        print("Invalid.")


def choose_runtime() -> str:
    print("\nChoose Container Runtime:")
    print(" 1. Docker")
    print(" 2. Podman")
    while True:
        c = input("Enter (1/2): ").strip()
        if c == "1":
            return "docker"
        if c == "2":
            return "podman"
        print("Invalid.")


# ----------------------------------------------------------------------
# Env / Kibana file generation
# ----------------------------------------------------------------------
def generate_env(vsphere, cloudinit, vm_specs, container_runtime, security):
    env_path = BASE / ".env"
    kibana_yml = BASE / "kibana" / "config" / "kibana.yml"
    kibana_yml.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Gather ES, Kibana, Fleet IPs & hostnames
    # ------------------------------------------------------------------
    es_nodes = [spec for name, spec in vm_specs.items() if "es-" in name.lower()]
    kibana_nodes = [spec for name, spec in vm_specs.items() if "kibana" in name.lower()]
    fleet_nodes = [spec for name, spec in vm_specs.items() if "fleet" in name.lower()]

    es_ips = ",".join(s["ip"] for s in es_nodes)
    es_hosts = ",".join(s["hostname"] for s in es_nodes)

    kibana_ip = kibana_nodes[0]["ip"] if kibana_nodes else ""
    kibana_host = kibana_nodes[0]["hostname"] if kibana_nodes else ""

    fleet_ip = fleet_nodes[0]["ip"] if fleet_nodes else kibana_ip
    fleet_host = fleet_nodes[0]["hostname"] if fleet_nodes else kibana_host

    # ------------------------------------------------------------------
    # Passwords & generic vars
    # ------------------------------------------------------------------
    passwords = {
        "ELASTIC_VERSION": "9.2.0",
        "ELASTIC_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "KIBANA_SYSTEM_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "LOGSTASH_INTERNAL_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "METRICBEAT_INTERNAL_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "FILEBEAT_INTERNAL_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "HEARTBEAT_INTERNAL_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "MONITORING_INTERNAL_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "BEATS_SYSTEM_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "ENT_SEARCH_DEFAULT_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "APM_SERVER_TOKEN": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "CONTAINER_RUNTIME": container_runtime,
        "ALLOWED_SUBNET": security["allowed_subnet"],
        # NEW: hostnames
        "ES_IPS": es_ips,
        "ES_HOSTS": es_hosts,
        "KIBANA_IP": kibana_ip,
        "KIBANA_HOST": kibana_host,
        "FLEET_IP": fleet_ip,
        "FLEET_HOST": fleet_host,
    }

    # vSphere vars
    passwords.update({
        "VCENTER_HOST": vsphere["vcenter_host"],
        "VCENTER_USER": vsphere["vcenter_user"],
        "VCENTER_PASSWORD": vsphere["vcenter_password"],
        "DATACENTER": vsphere["datacenter"],
        "CLUSTER": vsphere["cluster"],
        "DATASTORE": vsphere["datastore"],
        "TEMPLATE": vsphere["template"]
    })

    # Cloud-init vars
    passwords.update({
        "SSH_USER": cloudinit["ssh_user"],
        "SSH_KEY": "~/.ssh/id_rsa",
        "CLOUDINIT_NAMESERVERS": cloudinit["nameservers"],
        "CLOUDINIT_GATEWAY": cloudinit["gateway"],
        "CLOUDINIT_TIMEZONE": cloudinit["timezone"],
        "CLOUDINIT_PACKAGES": cloudinit["packages"]
    })

    # Write .env
    with open(env_path, "w") as f:
        for k, v in passwords.items():
            f.write(f"{k}={v}\n")
    print(f".env generated at {env_path}")

    # Kibana encryption keys
    enc_keys = [
        f"xpack.security.encryptionKey: {subprocess.getoutput('openssl rand -hex 48 | tr -d \"\\n\"')}",
        f"xpack.reporting.encryptionKey: {subprocess.getoutput('openssl rand -hex 48 | tr -d \"\\n\"')}",
        f"xpack.encryptedSavedObjects.encryptionKey: {subprocess.getoutput('openssl rand -hex 48 | tr -d \"\\n\"')}"
    ]
    with open(kibana_yml, "a") as f:
        for line in enc_keys:
            f.write(line + "\n")


# ----------------------------------------------------------------------
# Ansible wrapper
# ----------------------------------------------------------------------
def run_ansible_phase(tags: str) -> None:
    print(f"Running Ansible phase: {tags}")
    subprocess.run([
        "ansible-playbook",
        "-i", str(BASE / "inventory" / "hosts.ini"),
        str(BASE / "playbook.yml"),
        "--tags", tags
    ], check=True)


# ----------------------------------------------------------------------
# Main orchestration
# ----------------------------------------------------------------------
def main():
    print("=" * 70)
    print("ELASTIC vSPHERE FULL AUTOMATION ORCHESTRATOR")
    print("=" * 70)

    install_powercli()

    vsphere_cfg = prompt_vsphere()
    cloudinit_cfg = prompt_cloudinit()
    vm_specs = prompt_vm_specs()
    security_cfg = prompt_security()
    choose_distro()
    runtime = choose_runtime()

    generate_env(vsphere_cfg, cloudinit_cfg, vm_specs, runtime, security_cfg)

    # Export for Ansible modules that read env vars directly
    os.environ["CLOUDINIT_CONFIG"] = str(cloudinit_cfg)
    os.environ["VM_SPECS"] = json.dumps(vm_specs)   # JSON string for complex data

    print("\nStarting full automation...")
    provision_and_validate_vms(vm_specs)

    # === PHASE 1: OS TUNING + REBOOT ===
    run_ansible_phase("os_tuning")
    print("Waiting for VMs to reboot...")
    time.sleep(90)

    # === PHASE 2: CONTAINER RUNTIME ===
    run_ansible_phase("container_runtime")

    # === PHASE 3: SETUP + ELASTICSEARCH ===
    run_ansible_phase("setup,elastic_node")

    # === PHASE 4: KIBANA + FLEET ===
    run_ansible_phase("kibana_fleet")

    deploy_and_validate_stack()

    print("\nDEPLOYMENT COMPLETE!")
    kibana_ip = next((s["ip"] for s in vm_specs.values() if "kibana" in s["hostname"].lower()), None)
    print(f"Kibana: https://{kibana_ip}:5601")
    print(f"Fleet:   https://{kibana_ip}:8220")


if __name__ == "__main__":
    main()