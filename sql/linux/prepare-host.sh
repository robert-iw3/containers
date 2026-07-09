#!/bin/bash
# prepare-host.sh: Optimize Linux host for SQL Server 2025 container

# Check if root
if [ "$EUID" -ne 0 ]; then
  echo "Run as root/sudo"
  exit 1
fi

# Install Docker (if not present)
if ! command -v docker &> /dev/null; then
  apt update -y
  apt install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt update -y
  apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi

# For Podman alternative: Uncomment if preferred (similar commands)
# apt install -y podman podman-compose

# Optimize kernel settings
echo "Disabling THP..."
echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo "Setting swappiness to 1..."
sysctl vm.swappiness=1
echo "vm.swappiness=1" >> /etc/sysctl.conf

# For RHEL/SUSE: Install and activate TuneD mssql profile (comment out if not RHEL)
# dnf install -y tuned tuned-profiles-mssql  # For RHEL
# systemctl enable --now tuned
# tuned-adm profile mssql

# Create data directory for volume (use ext4 for best perf)
mkdir -p /var/sql-data
chown -R $(whoami) /var/sql-data  # Adjust owner if needed
mkfs.ext4 /dev/sdX  # Format a dedicated disk if available (replace sdX); mount to /var/sql-data

echo "Host prepared. Deploy with docker compose up."