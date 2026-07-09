import os
import subprocess
import tempfile
import platform
import shutil
import sys
import psutil
from pathlib import Path

def status(msg):
    print(f">>> {msg}", file=sys.stderr)

def error(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def warning(msg):
    print(f"WARNING: {msg}", file=sys.stderr)

def check_available(tool):
    return shutil.which(tool) is not None

def install_ollama():
    if platform.system() != "Linux":
        error("This script is intended to run on Linux only.")

    arch_map = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
    arch = platform.machine()
    if arch not in arch_map:
        error(f"Unsupported architecture: {arch}")
    ollama_arch = arch_map[arch]

    sudo = "" if os.getuid() == 0 else "sudo"
    if sudo and not check_available("sudo"):
        error("This script requires superuser permissions. Please re-run as root.")

    required_tools = ["curl", "awk", "grep", "sed", "tee", "xargs"]
    missing = [tool for tool in required_tools if not check_available(tool)]
    if missing:
        error(f"The following tools are required but missing: {', '.join(missing)}")

    with tempfile.TemporaryDirectory() as temp_dir:
        ollama_url = f"https://ollama.ai/download/ollama-linux-{ollama_arch}"
        ollama_path = Path(temp_dir) / "ollama"
        status("Downloading ollama...")
        subprocess.run(["curl", "--fail", "--show-error", "--location", "--progress-bar", "-o", str(ollama_path), ollama_url], check=True)

        for bindir in ["/usr/local/bin", "/usr/bin", "/bin"]:
            if bindir in os.environ["PATH"]:
                break
        status(f"Installing ollama to {bindir}...")
        subprocess.run([sudo, "install", "-o0", "-g0", "-m755", "-d", bindir], check=True)
        subprocess.run([sudo, "install", "-o0", "-g0", "-m755", str(ollama_path), f"{bindir}/ollama"], check=True)
        status('Install complete. Run "ollama" from the command line.')

        # Optional: Systemd service
        if check_available("systemctl"):
            if not subprocess.run(["id", "ollama"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
                status("Creating ollama user...")
                subprocess.run([sudo, "useradd", "-r", "-s", "/bin/false", "-m", "-d", "/usr/share/ollama", "ollama"], check=True)

            status("Creating ollama systemd service...")
            service_content = f"""[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart={bindir}/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="HOME=/usr/share/ollama"
Environment="PATH={os.environ['PATH']}"

[Install]
WantedBy=default.target
"""
            with open("/tmp/ollama.service", "w") as f:
                f.write(service_content)
            subprocess.run([sudo, "tee", "/etc/systemd/system/ollama.service"], input=service_content.encode(), check=True)

            systemctl_status = subprocess.run(["systemctl", "is-system-running"], capture_output=True, text=True).stdout.strip()
            if systemctl_status in ["running", "degraded"]:
                status("Enabling and starting ollama service...")
                subprocess.run([sudo, "systemctl", "daemon-reload"], check=True)
                subprocess.run([sudo, "systemctl", "enable", "ollama"], check=True)
                subprocess.run([sudo, "systemctl", "restart", "ollama"], check=True)

        # Optional: CUDA drivers
        if check_available("nvidia-smi") and subprocess.run(["nvidia-smi"], capture_output=True).returncode == 0:
            status("NVIDIA GPU installed.")
            return

        if not (check_available("lspci") and subprocess.run(["lspci", "-d", "10de:"], capture_output=True, text=True).stdout.strip()) and \
           not (check_available("lshw") and subprocess.run([sudo, "lshw", "-c", "display", "-numeric"], capture_output=True, text=True).stdout.strip()):
            warning("No NVIDIA GPU detected. Ollama will run in CPU-only mode.")
            return

        os_release = {}
        with open("/etc/os-release") as f:
            for line in f:
                k, v = line.strip().split("=", 1)
                os_release[k] = v.strip('"')
        os_name = os_release.get("ID")
        os_version = os_release.get("VERSION_ID")

        package_managers = ["dnf", "yum", "apt-get"]
        package_manager = next((pm for pm in package_managers if check_available(pm)), None)
        if not package_manager:
            error("Unknown package manager. Skipping CUDA installation.")

        def install_cuda_yum(os_type, version):
            status("Installing NVIDIA repository...")
            repo_url = f"https://developer.download.nvidia.com/compute/cuda/repos/{os_type}{version}/{platform.machine()}/cuda-{os_type}{version}.repo"
            if package_manager == "yum":
                subprocess.run([sudo, package_manager, "-y", "install", "yum-utils"], check=True)
                subprocess.run([sudo, f"{package_manager}-config-manager", "--add-repo", repo_url], check=True)
            else:
                subprocess.run([sudo, package_manager, "config-manager", "--add-repo", repo_url], check=True)
            if os_type == "rhel":
                status("Installing EPEL repository...")
                subprocess.run([sudo, package_manager, "-y", "install", f"https://dl.fedoraproject.org/pub/epel/epel-release-latest-{version}.noarch.rpm"], check=True)
            status("Installing CUDA driver...")
            if os_type == "centos" or os_type + version == "rhel7":
                subprocess.run([sudo, package_manager, "-y", "install", "nvidia-driver-latest-dkms"], check=True)
            subprocess.run([sudo, package_manager, "-y", "install", "cuda-drivers"], check=True)

        def install_cuda_apt(os_type, version):
            status("Installing NVIDIA repository...")
            keyring_url = f"https://developer.download.nvidia.com/compute/cuda/repos/{os_type}{version}/{platform.machine()}/cuda-keyring_1.1-1_all.deb"
            keyring_path = Path(temp_dir) / "cuda-keyring.deb"
            subprocess.run(["curl", "-fsSL", "-o", str(keyring_path), keyring_url], check=True)
            if os_type == "debian":
                status("Enabling contrib sources...")
                subprocess.run([sudo, "sed", "s/main/contrib/", "-i", "/etc/apt/sources.list.d/contrib.list"], check=True)
            status("Installing CUDA driver...")
            subprocess.run([sudo, "dpkg", "-i", str(keyring_path)], check=True)
            subprocess.run([sudo, "apt-get", "update"], check=True)
            subprocess.run([sudo, "-E", "DEBIAN_FRONTEND=noninteractive", "apt-get", "-y", "install", "cuda-drivers", "-q"], check=True)

        if not subprocess.run(["nvidia-smi"], capture_output=True).returncode == 0 or "CUDA Version" not in subprocess.run(["nvidia-smi"], capture_output=True, text=True).stdout:
            if os_name in ["centos", "rhel"]:
                install_cuda_yum("rhel", os_version)
            elif os_name == "rocky":
                install_cuda_yum("rhel", os_version.split(".")[0])
            elif os_name == "fedora":
                install_cuda_yum("fedora", os_version)
            elif os_name == "amzn":
                install_cuda_yum("fedora", "35")
            elif os_name in ["debian", "ubuntu"]:
                install_cuda_apt(os_name, os_version.replace(".", "") if os_name == "ubuntu" else os_version)
            else:
                return

        if not subprocess.run(["lsmod"], capture_output=True, text=True).stdout.strip():
            kernel_release = platform.release()
            if os_name in ["centos", "rhel", "rocky", "amzn"]:
                subprocess.run([sudo, package_manager, "-y", "install", f"kernel-devel-{kernel_release}", f"kernel-headers-{kernel_release}"], check=True)
            elif os_name == "fedora":
                subprocess.run([sudo, package_manager, "-y", "install", f"kernel-devel-{kernel_release}"], check=True)
            elif os_name in ["debian", "ubuntu"]:
                subprocess.run([sudo, "apt-get", "-y", "install", f"linux-headers-{kernel_release}"], check=True)

            dkms_status = subprocess.run([sudo, "dkms", "status"], capture_output=True, text=True).stdout
            nvidia_version = next((line.split(":")[0] for line in dkms_status.splitlines() if "added" in line), None)
            if nvidia_version:
                subprocess.run([sudo, "dkms", "install", nvidia_version], check=True)

            if "nouveau" in subprocess.run(["lsmod"], capture_output=True, text=True).stdout:
                status("Reboot to complete NVIDIA CUDA driver install.")
                return
            subprocess.run([sudo, "modprobe", "nvidia"], check=True)

        status("NVIDIA CUDA drivers installed.")

if __name__ == "__main__":
    install_ollama()