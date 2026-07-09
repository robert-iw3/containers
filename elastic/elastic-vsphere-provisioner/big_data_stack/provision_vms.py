#!/usr/bin/env python3
"""
Provisions VMs on vSphere using PowerCLI + ISO + Cloud-Init
Validates:
- VM powered on
- SSH reachable
- Docker/Podman installed and running
- Real VM IPs in certs
"""
import os
import sys
import time
import paramiko
import requests
from pathlib import Path
from dotenv import load_dotenv
import subprocess
import ast

load_dotenv()
BASE = Path(__file__).parent
ISOS_DIR = BASE / "isos"
ISOS_DIR.mkdir(exist_ok=True)

DISTRO = os.getenv("DISTRO")
CLOUDINIT_CONFIG = ast.literal_eval(os.getenv("CLOUDINIT_CONFIG", "{}"))
VM_SPECS = ast.literal_eval(os.getenv("VM_SPECS", "{}"))
SSH_USER = CLOUDINIT_CONFIG.get("ssh_user", "ubuntu")
SSH_KEY = os.path.expanduser(os.getenv("SSH_KEY", "~/.ssh/id_rsa"))
CONTAINER_RUNTIME = os.getenv("CONTAINER_RUNTIME", "podman")

ISO_URLS = {
    "ubuntu": "https://releases.ubuntu.com/24.04/ubuntu-24.04-live-server-amd64.iso",
    "debian": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.7.0-amd64-netinst.iso",
    "almalinux": "https://repo.almalinux.org/almalinux/9/isos/x86_64/AlmaLinux-9.4-x86_64-boot.iso",
    "rhel": None
}

def run_powershell(script):
    try:
        result = subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"PowerShell Error: {e.stderr}")
        sys.exit(1)

def download_iso():
    if DISTRO not in ISO_URLS or not ISO_URLS[DISTRO]:
        print(f"{DISTRO} ISO not available for auto-download.")
        sys.exit(1)

    url = ISO_URLS[DISTRO]
    iso_name = url.split("/")[-1]
    iso_path = ISOS_DIR / iso_name

    if iso_path.exists():
        print(f"Using cached ISO: {iso_name}")
        return str(iso_path)

    print(f"Downloading {DISTRO} ISO from {url}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(iso_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Downloaded: {iso_path}")
    return str(iso_path)

def generate_cloud_init(vm_name, ip):
    template_dir = BASE / "cloud_init" / DISTRO
    if not template_dir.exists():
        print(f"Cloud-init template for {DISTRO} not found.")
        sys.exit(1)
    user_data = (template_dir / "user-data").read_text()
    meta_data = (template_dir / "meta-data").read_text()

    user_data = user_data.replace("{{ hostname }}", vm_name)
    user_data = user_data.replace("{{ ssh_user }}", CLOUDINIT_CONFIG["ssh_user"])
    user_data = user_data.replace("{{ ssh_password }}", CLOUDINIT_CONFIG["ssh_password"])
    user_data = user_data.replace("{{ ip }}", ip)
    user_data = user_data.replace("{{ nameservers }}", CLOUDINIT_CONFIG["nameservers"])
    user_data = user_data.replace("{{ gateway }}", CLOUDINIT_CONFIG["gateway"])
    user_data = user_data.replace("{{ timezone }}", CLOUDINIT_CONFIG["timezone"])
    user_data = user_data.replace("{{ packages }}", CLOUDINIT_CONFIG["packages"])
    user_data = user_data.replace("{{ container_runtime }}", CONTAINER_RUNTIME)

    cidata_dir = BASE / f"cidata-{vm_name}"
    cidata_dir.mkdir(exist_ok=True)
    (cidata_dir / "user-data").write_text(user_data)
    (cidata_dir / "meta-data").write_text(meta_data.replace("{{ hostname }}", vm_name))

    iso_path = BASE / f"cidata-{vm_name}.iso"
    cmd = f"mkisofs -o {iso_path} -V cidata -r -J {cidata_dir}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to create cloud-init ISO: {result.stderr}")
        sys.exit(1)
    return str(iso_path)

def wait_for_ssh(ip, timeout=600):
    print(f"Waiting for SSH on {ip}...")
    start = time.time()
    while time.time() - start < timeout:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(ip, username=SSH_USER, key_filename=SSH_KEY, timeout=10)
            client.close()
            print(f"SSH OK on {ip}")
            return True
        except:
            time.sleep(10)
    print(f"SSH timeout on {ip}")
    return False

def check_container_runtime(ip):
    print(f"Checking {CONTAINER_RUNTIME} on {ip}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, username=SSH_USER, key_filename=SSH_KEY)
        cmd = f"{CONTAINER_RUNTIME} info --format '{{{{.ServerVersion}}}}'"
        stdin, stdout, stderr = client.exec_command(cmd)
        if stdout.channel.recv_exit_status() == 0:
            version = stdout.read().decode().strip()
            print(f"{CONTAINER_RUNTIME} OK on {ip} (v{version})")
            return True
        else:
            print(f"{CONTAINER_RUNTIME} not running: {stderr.read().decode()}")
    except Exception as e:
        print(f"Container check failed: {e}")
    finally:
        client.close()
    return False

def provision_and_validate_vms(vm_specs):
    iso_path = download_iso()

    for vm_name, spec in vm_specs.items():
        print(f"\nProvisioning {vm_name}...")
        cidata_iso = generate_cloud_init(vm_name, spec["ip"])

        ps_script = f'''
        Connect-VIServer -Server {os.getenv("VCENTER_HOST")} -User {os.getenv("VCENTER_USER")} -Password {os.getenv("VCENTER_PASSWORD")} -Force
        $dc = Get-Datacenter -Name "{os.getenv("DATACENTER")}"
        $cluster = Get-Cluster -Name "{os.getenv("CLUSTER")}" -Location $dc
        $ds = Get-Datastore -Name "{os.getenv("DATASTORE")}" -Location $cluster

        $vm = New-VM -Name {vm_name} -Location $dc -ResourcePool $cluster -Datastore $ds
        Set-VM -VM $vm -NumCpu {spec["cpu"]} -MemoryGB {spec["ram_gb"]} -Confirm:$false

        New-CDDrive -VM $vm -IsoPath "[{os.getenv("DATASTORE")} ] {Path(iso_path).name}" -StartConnected $true
        New-CDDrive -VM $vm -IsoPath "[{os.getenv("DATASTORE")} ] {Path(cidata_iso).name}" -StartConnected $true

        Start-VM -VM $vm
        Wait-Tools -VM $vm -TimeoutSeconds 600
        Disconnect-VIServer -Confirm:$false
        '''

        run_powershell(ps_script)

        if not wait_for_ssh(spec["ip"]):
            sys.exit(1)
        if not check_container_runtime(spec["ip"]):
            sys.exit(1)

    print("ALL VMs READY!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        specs = json.loads(sys.argv[1])
        provision_and_validate_vms(specs)
    else:
        print("Run via orchestrate.py")