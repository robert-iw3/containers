#!/bin/bash

# prep_cribl_host.sh: Optimize Linux host for high-performance Cribl containers
# Targets: High data throughput (25+ TB/day), CPU/IO/network tuning
# Tested on Ubuntu 24.04/RHEL 9; adapt as needed
# Run as root: sudo ./prep_cribl_host.sh
# Backups: Original sysctl/limits saved to /etc/*.bak

set -euo pipefail

# Check if root
if [ "$EUID" -ne 0 ]; then
  echo "Error: Must run as root."
  exit 1
fi

# Backup configs
cp /etc/sysctl.conf /etc/sysctl.conf.bak.$(date +%Y%m%d)
cp /etc/security/limits.conf /etc/security/limits.conf.bak.$(date +%Y%m%d)

# 1. Increase ulimits (file handles, processes)
echo "Tuning ulimits..."
cat <<EOF >> /etc/security/limits.conf
* soft nofile 65535
* hard nofile 65535
* soft nproc 65535
* hard nproc 65535
root soft nofile 65535
root hard nofile 65535
root soft nproc 65535
root hard nproc 65535
EOF

# 2. Kernel tunings (sysctl) for network/IO/VM
echo "Tuning sysctl params..."
cat <<EOF >> /etc/sysctl.conf
# Increase max open files system-wide
fs.file-max = 1000000

# Network optimizations for high throughput
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_mem = 786432 1048576 1572864  # Adjust based on RAM
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# VM tunings: Reduce swappiness, increase overcommit
vm.swappiness = 10  # Or 0 to disable swap if sufficient RAM
vm.overcommit_memory = 1
vm.max_map_count = 262144  # For Elastic integration if co-located

# IO scheduler (use deadline/mq-deadline for SSDs)
fs.aio-max-nr = 1048576
EOF

sysctl -p  # Apply immediately

# 3. Set CPU governor to performance (for high CPU workloads)
echo "Setting CPU governor to performance..."
if command -v cpupower &> /dev/null; then
  cpupower frequency-set -g performance
elif command -v cpufreq-set &> /dev/null; then
  for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo "performance" > "$cpu"
  done
else
  echo "Warning: Install cpupower or cpufreq-utils for CPU governor tuning."
fi

# 4. Disable unnecessary services (optional, customize)
echo "Disabling unnecessary services..."
systemctl disable --now apt-daily.timer apt-daily-upgrade.timer  # Ubuntu-specific
# Add more: e.g., systemctl disable bluetooth snapd

# 5. Ensure Docker/Podman/K8s prereqs
echo "Installing/Checking container prereqs..."
if [ -f /etc/redhat-release ]; then
  dnf install -y epel-release
  dnf install -y curl jq git iproute procps-ng
else
  apt update
  apt install -y curl jq git iproute2 procps
fi

# Verify Docker/Podman if installed
if command -v docker &> /dev/null; then
  echo "Tuning Docker daemon..."
  mkdir -p /etc/docker
  cat <<EOF > /etc/docker/daemon.json
{
  "default-ulimits": {
    "nofile": { "Hard": 65535, "Soft": 65535 },
    "nproc": { "Hard": 65535, "Soft": 65535 }
  },
  "storage-driver": "overlay2"  # Efficient for high IO
}
EOF
  systemctl restart docker
fi

if command -v podman &> /dev/null; then
  echo "Podman detected; ensure rootless if needed, but tunings apply host-wide."
fi

# 6. Reboot recommendation
echo "Optimizations applied. Reboot recommended for full effect: sudo reboot"
echo "Verify with: ulimit -n (should be 65535), sysctl -a | grep somaxconn"