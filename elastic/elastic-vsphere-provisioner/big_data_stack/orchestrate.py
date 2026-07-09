#!/usr/bin/env python3
"""
Elastic vSphere Full Automation Orchestrator
Features:
- Prompt for .env OR auto-generate with random passwords
- Install PowerCLI
- Choose distro
- Download ISO
- Provision VMs
- Choose Docker/Podman
- Deploy + Validate
"""
import os
import sys
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

def run_powershell(script):
    """Run PowerShell script and return output"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"PowerShell Error: {e.stderr}")
        sys.exit(1)

def check_powercli():
    """Check if PowerCLI is installed"""
    script = "if (Get-Module -ListAvailable -Name VMware.PowerCLI) { 'INSTALLED' } else { 'MISSING' }"
    output = run_powershell(script).strip()
    return output == "INSTALLED"

def install_powercli():
    """Install PowerCLI if not present"""
    if check_powercli():
        print("PowerCLI already installed.")
        return
    print("Installing PowerCLI...")
    if not POWERSHELL_SCRIPT.exists():
        print(f"ERROR: {POWERSHELL_SCRIPT} missing!")
        sys.exit(1)
    output = run_powershell(f"Get-Content '{POWERSHELL_SCRIPT}' -Raw | Invoke-Expression")
    print(output)

def generate_env():
    """Auto-generate .env with random passwords"""
    print("Generating .env with random passwords...")
    env_path = BASE / ".env"
    kibana_yml = BASE / "kibana" / "config" / "kibana.yml"

    # Create directories
    kibana_yml.parent.mkdir(parents=True, exist_ok=True)

    # Generate passwords
    passwords = {
        "ELASTIC_VERSION": "9.2.0",
        "ELASTIC_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "LOGSTASH_INTERNAL_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "KIBANA_SYSTEM_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "METRICBEAT_INTERNAL_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "FILEBEAT_INTERNAL_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "HEARTBEAT_INTERNAL_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "MONITORING_INTERNAL_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "BEATS_SYSTEM_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "ENT_SEARCH_DEFAULT_PASSWORD": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "APM_SERVER_TOKEN": subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'"),
        "VCENTER_HOST": "vcenter.example.com",
        "VCENTER_USER": "admin@vsphere.local",
        "VCENTER_PASSWORD": "your_password",
        "DATACENTER": "Datacenter",
        "CLUSTER": "Cluster",
        "DATASTORE": "datastore1",
        "TEMPLATE": "ubuntu-template",
        "SSH_USER": "ubuntu",
        "SSH_KEY": "~/.ssh/id_rsa"
    }

    # Write .env
    with open(env_path, "w") as f:
        for k, v in passwords.items():
            f.write(f"{k}={v}\n")
    print(f".env generated at {env_path}")

    # Generate Kibana encryption keys
    encryption_keys = [
        f"xpack.security.encryptionKey: {subprocess.getoutput('openssl rand -hex 48 | tr -d \"\\n\"')}",
        f"xpack.reporting.encryptionKey: {subprocess.getoutput('openssl rand -hex 48 | tr -d \"\\n\"')}",
        f"xpack.encryptedSavedObjects.encryptionKey: {subprocess.getoutput('openssl rand -hex 48 | tr -d \"\\n\"')}"
    ]
    with open(kibana_yml, "a") as f:
        for line in encryption_keys:
            f.write(line + "\n")
    print(f"Kibana encryption keys added to {kibana_yml}")

def prompt_env():
    """Prompt user for .env values"""
    print("Enter vSphere and Elastic credentials:")
    vcenter_host = input("vCenter Host: ").strip() or "vcenter.example.com"
    vcenter_user = input("vCenter User: ").strip() or "admin@vsphere.local"
    vcenter_password = input("vCenter Password: ").strip()
    datacenter = input("Datacenter: ").strip() or "Datacenter"
    cluster = input("Cluster: ").strip() or "Cluster"
    datastore = input("Datastore: ").strip() or "datastore1"
    template = input("VM Template: ").strip() or "ubuntu-template"
    ssh_user = input("SSH User: ").strip() or "ubuntu"
    ssh_key = input("SSH Key Path: ").strip() or "~/.ssh/id_rsa"

    elastic_password = input("Elastic Password (or press Enter for random): ").strip()
    if not elastic_password:
        elastic_password = subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'")

    kibana_password = input("Kibana System Password (or press Enter for random): ").strip()
    if not kibana_password:
        kibana_password = subprocess.getoutput("openssl rand -hex 36 | tr -d '\n'")

    # Save to .env
    env_path = BASE / ".env"
    with open(env_path, "w") as f:
        f.write(f"ELASTIC_VERSION=9.2.0\n")
        f.write(f"ELASTIC_PASSWORD={elastic_password}\n")
        f.write(f"KIBANA_SYSTEM_PASSWORD={kibana_password}\n")
        f.write(f"VCENTER_HOST={vcenter_host}\n")
        f.write(f"VCENTER_USER={vcenter_user}\n")
        f.write(f"VCENTER_PASSWORD={vcenter_password}\n")
        f.write(f"DATACENTER={datacenter}\n")
        f.write(f"CLUSTER={cluster}\n")
        f.write(f"DATASTORE={datastore}\n")
        f.write(f"TEMPLATE={template}\n")
        f.write(f"SSH_USER={ssh_user}\n")
        f.write(f"SSH_KEY={ssh_key}\n")
    print(f".env saved to {env_path}")

def choose_distro():
    """Choose Linux distribution"""
    print("Choose Linux Distro:")
    for i, d in enumerate(DISTROS, 1):
        print(f"  {i}. {d.capitalize()}")
    while True:
        c = input("Enter (1-4): ").strip()
        if c in ["1", "2", "3", "4"]:
            distro = DISTROS[int(c) - 1]
            os.environ["DISTRO"] = distro
            print(f"Selected: {distro.upper()}")
            return distro
        print("Invalid choice.")

def main():
    print("=" * 70)
    print("ELASTIC vSPHERE FULL AUTOMATION ORCHESTRATOR")
    print("=" * 70)

    # 1. .env setup
    if not (BASE / ".env").exists():
        choice = input("Generate .env automatically? (y/n): ").strip().lower()
        if choice == "y":
            generate_env()
        else:
            prompt_env()
    else:
        print(".env already exists. Using it.")

    # 2. Install PowerCLI
    install_powercli()

    # 3. Choose distro
    choose_distro()

    # 4. Full flow
    print("\nStarting full automation...")
    provision_and_validate_vms()
    deploy_and_validate_stack()

    print("\nDEPLOYMENT COMPLETE!")
    print("Kibana: https://192.168.1.14:5601")
    print("Fleet:  https://192.168.1.14:8220")

if __name__ == "__main__":
    main()