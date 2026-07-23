#!/bin/bash
# Installs Ollama on Linux with architecture detection and optional CUDA setup.

set -eu

status() { echo ">>> $*" >&2; }
error() { echo "ERROR: $*" >&2; exit 1; }
warning() { echo "WARNING: $*" >&2; }

TEMP_DIR=$(mktemp -d)
cleanup() { rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

check_available() { command -v "$1" >/dev/null; }

[ "$(uname -s)" = "Linux" ] || error "This script runs on Linux only."

case "$(uname -m)" in
    x86_64) ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *) error "Unsupported architecture: $(uname -m)" ;;
esac

SUDO=""
if [ "$(id -u)" -ne 0 ] && ! check_available sudo; then
    error "Superuser permissions required. Please re-run as root or install sudo."
fi
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

for tool in curl awk grep sed tee; do
    check_available "$tool" || error "Required tool missing: $tool"
done

status "Downloading ollama..."
curl --fail --show-error --location --progress-bar -o "$TEMP_DIR/ollama" "https://ollama.ai/download/ollama-linux-$ARCH"

for BINDIR in /usr/local/bin /usr/bin /bin; do
    echo "$PATH" | grep -q "$BINDIR" && break
done

status "Installing ollama to $BINDIR..."
$SUDO install -o0 -g0 -m755 -d "$BINDIR"
$SUDO install -o0 -g0 -m755 "$TEMP_DIR/ollama" "$BINDIR/ollama"

trap 'status "Install complete. Run \"ollama\" from the command line."' EXIT

# Optional: Systemd service
if check_available systemctl; then
    if ! id ollama >/dev/null 2>&1; then
        status "Creating ollama user..."
        $SUDO useradd -r -s /bin/false -m -d /usr/share/ollama ollama
    fi

    status "Creating ollama systemd service..."
    cat <<EOF | $SUDO tee /etc/systemd/system/ollama.service >/dev/null
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=$BINDIR/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="HOME=/usr/share/ollama"
Environment="PATH=$PATH"

[Install]
WantedBy=default.target
EOF

    if systemctl is-system-running >/dev/null; then
        status "Enabling and starting ollama service..."
        $SUDO systemctl daemon-reload
        $SUDO systemctl enable ollama
        $SUDO systemctl restart ollama
    fi
fi

# Optional: CUDA drivers
if check_available nvidia-smi && nvidia-smi >/dev/null 2>&1; then
    status "NVIDIA GPU installed."
    exit 0
fi

if ! { check_available lspci && lspci -d '10de:' | grep -q 'NVIDIA'; } && \
   ! { check_available lshw && $SUDO lshw -c display -numeric | grep -q 'vendor: .* \[10DE\]'; }; then
    warning "No NVIDIA GPU detected. Ollama will run in CPU-only mode."
    exit 0
fi

if [ ! -f /etc/os-release ]; then
    error "Unknown distribution. Skipping CUDA installation."
fi

. /etc/os-release
OS_NAME=$ID
OS_VERSION=$VERSION_ID

for PM in dnf yum apt-get; do
    check_available "$PM" && PACKAGE_MANAGER="$PM" && break
done
[ -z "$PACKAGE_MANAGER" ] && error "Unknown package manager. Skipping CUDA installation."

install_cuda_yum() {
    status "Installing NVIDIA repository..."
    if [ "$PACKAGE_MANAGER" = "yum" ]; then
        $SUDO $PACKAGE_MANAGER -y install yum-utils
        $SUDO $PACKAGE_MANAGER-config-manager --add-repo "https://developer.download.nvidia.com/compute/cuda/repos/$1$2/$(uname -m)/cuda-$1$2.repo"
    else
        $SUDO $PACKAGE_MANAGER config-manager --add-repo "https://developer.download.nvidia.com/compute/cuda/repos/$1$2/$(uname -m)/cuda-$1$2.repo"
    fi
    [ "$1" = "rhel" ] && $SUDO $PACKAGE_MANAGER -y install "https://dl.fedoraproject.org/pub/epel/epel-release-latest-$2.noarch.rpm" || true
    status "Installing CUDA driver..."
    [ "$1" = "centos" ] || [ "$1$2" = "rhel7" ] && $SUDO $PACKAGE_MANAGER -y install nvidia-driver-latest-dkms
    $SUDO $PACKAGE_MANAGER -y install cuda-drivers
}

install_cuda_apt() {
    status "Installing NVIDIA repository..."
    curl -fsSL -o "$TEMP_DIR/cuda-keyring.deb" "https://developer.download.nvidia.com/compute/cuda/repos/$1$2/$(uname -m)/cuda-keyring_1.1-1_all.deb"
    [ "$1" = "debian" ] && $SUDO sed -i 's/main/contrib/' /etc/apt/sources.list.d/contrib.list
    status "Installing CUDA driver..."
    $SUDO dpkg -i "$TEMP_DIR/cuda-keyring.deb"
    $SUDO apt-get update
    $SUDO DEBIAN_FRONTEND=noninteractive apt-get -y install cuda-drivers -q
}

if ! { nvidia-smi |& grep -q "CUDA Version"; }; then
    case $OS_NAME in
        centos|rhel) install_cuda_yum rhel "$OS_VERSION" ;;
        rocky) install_cuda_yum rhel "${OS_VERSION%%.*}" ;;
        fedora) install_cuda_yum fedora "$OS_VERSION" ;;
        amzn) install_cuda_yum fedora 35 ;;
        debian) install_cuda_apt debian "$OS_VERSION" ;;
        ubuntu) install_cuda_apt ubuntu "${OS_VERSION//./}" ;;
        *) exit 0 ;;
    esac
fi

if ! lsmod | grep -q nvidia; then
    KERNEL_RELEASE="$(uname -r)"
    case $OS_NAME in
        centos|rhel|rocky|amzn) $SUDO $PACKAGE_MANAGER -y install "kernel-devel-$KERNEL_RELEASE" "kernel-headers-$KERNEL_RELEASE" ;;
        fedora) $SUDO $PACKAGE_MANAGER -y install "kernel-devel-$KERNEL_RELEASE" ;;
        debian|ubuntu) $SUDO apt-get -y install "linux-headers-$KERNEL_RELEASE" ;;
        *) exit 0 ;;
    esac

    NVIDIA_CUDA_VERSION=$($SUDO dkms status | awk -F: '/added/ { print $1 }')
    [ -n "$NVIDIA_CUDA_VERSION" ] && $SUDO dkms install "$NVIDIA_CUDA_VERSION"

    if lsmod | grep -q nouveau; then
        status "Reboot to complete NVIDIA CUDA driver install."
        exit 0
    fi
    $SUDO modprobe nvidia
fi

status "NVIDIA CUDA drivers installed."