#!/bin/bash
# Install HashiCorp Nomad on Debian or Red Hat-based systems.
# This is the single-host quickstart avenue. For a real multi-node production
# cluster use ../ansible/ or ../terraform/ instead (see ../readme.md).

set -euo pipefail

NOMAD_VERSION="${NOMAD_VERSION:-2.0.3}"
case "$(uname -m)" in
    x86_64) ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    *) echo "Unsupported architecture: $(uname -m)"; exit 1 ;;
esac
NOMAD_ZIP="nomad_${NOMAD_VERSION}_linux_${ARCH}.zip"
NOMAD_URL="https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/${NOMAD_ZIP}"
NOMAD_SHA_URL="https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/nomad_${NOMAD_VERSION}_SHA256SUMS"
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="/etc/nomad.d"
DATA_DIR="/opt/nomad/data"

if [ -f /etc/debian_version ]; then
    OS="debian"
    PKG_MANAGER="apt-get"
elif [ -f /etc/redhat-release ]; then
    OS="redhat"
    PKG_MANAGER="yum"
else
    echo "Unsupported OS. This script supports Debian/Ubuntu or RHEL/CentOS."
    exit 1
fi

echo "Installing dependencies..."
if [ "$OS" = "debian" ]; then
    sudo "$PKG_MANAGER" update -y
    sudo "$PKG_MANAGER" install -y unzip curl
elif [ "$OS" = "redhat" ]; then
    sudo "$PKG_MANAGER" install -y unzip curl
fi

echo "Downloading Nomad ${NOMAD_VERSION}..."
curl -sSL "$NOMAD_URL" -o "/tmp/${NOMAD_ZIP}"
curl -sSL "$NOMAD_SHA_URL" -o "/tmp/nomad_${NOMAD_VERSION}_SHA256SUMS"

echo "Verifying checksum..."
EXPECTED_SHA=$(grep "${NOMAD_ZIP}" "/tmp/nomad_${NOMAD_VERSION}_SHA256SUMS" | awk '{print $1}')
if [ -z "$EXPECTED_SHA" ]; then
    echo "Could not find a checksum for ${NOMAD_ZIP} in the release SHA256SUMS file"
    exit 1
fi
ACTUAL_SHA=$(sha256sum "/tmp/${NOMAD_ZIP}" | awk '{print $1}')
if [ "$EXPECTED_SHA" != "$ACTUAL_SHA" ]; then
    echo "Checksum mismatch: expected ${EXPECTED_SHA}, got ${ACTUAL_SHA}"
    exit 1
fi

echo "Installing Nomad..."
sudo unzip -o "/tmp/${NOMAD_ZIP}" -d "$INSTALL_DIR"
sudo chmod +x "${INSTALL_DIR}/nomad"
rm "/tmp/${NOMAD_ZIP}" "/tmp/nomad_${NOMAD_VERSION}_SHA256SUMS"

nomad version

echo "Setting up Nomad directories..."
sudo useradd --system --shell /sbin/nologin --home-dir /home/nomad nomad 2>/dev/null || true
sudo mkdir -p "$CONFIG_DIR" "$DATA_DIR"
sudo chown -R nomad:nomad "$CONFIG_DIR" "$DATA_DIR"
sudo chmod 750 "$CONFIG_DIR" "$DATA_DIR"

if ! command -v nomad &> /dev/null; then
    echo "Nomad binary not found in PATH. Please ensure ${INSTALL_DIR} is in your PATH."
    exit 1
fi

echo "Nomad installation completed successfully!"
echo "Next steps:"
echo "1. Configure Nomad by editing ${CONFIG_DIR}/nomad.hcl (see nomad.hcl in this directory for a single-node example)"
echo "2. Install the systemd unit with: sudo ./install-nomad-systemd.sh"
echo "3. Start Nomad with: sudo systemctl start nomad"
