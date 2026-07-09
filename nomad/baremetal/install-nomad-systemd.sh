#!/bin/bash
# Installs the Nomad systemd unit from this repository's own vendored copy
# instead of fetching it from the network at install time.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v dnf &>/dev/null; then
  SYSTEMD_DIR="/etc/systemd/system"
  echo "Installing systemd services for RHEL/CentOS"
elif command -v apt-get &>/dev/null; then
  SYSTEMD_DIR="/lib/systemd/system"
  echo "Installing systemd services for Debian/Ubuntu"
else
  echo "Service not installed due to OS detection failure"
  exit 1
fi

sudo cp "${SCRIPT_DIR}/nomad.service" "${SYSTEMD_DIR}/nomad.service"
sudo cp "${SCRIPT_DIR}/init/systemd/nomad-online.target" "${SYSTEMD_DIR}/nomad-online.target"
sudo cp "${SCRIPT_DIR}/init/systemd/nomad-online.service" "${SYSTEMD_DIR}/nomad-online.service"
sudo install -m 0755 "${SCRIPT_DIR}/init/systemd/nomad-online.sh" /usr/bin/nomad-online.sh
sudo chmod 0644 "${SYSTEMD_DIR}/nomad.service" "${SYSTEMD_DIR}/nomad-online.target" "${SYSTEMD_DIR}/nomad-online.service"

sudo systemctl daemon-reload
sudo systemctl enable nomad nomad-online.service
sudo systemctl start nomad

echo "Complete"