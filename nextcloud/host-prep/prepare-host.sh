#!/bin/bash
# Prepare a fresh Linux host (Ubuntu/Debian or RHEL-family) to run the
# Nextcloud stack: kernel/net tuning, firewall openings, docker checks.
# Run as root: sudo ./prepare-host.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (sudo $0)" >&2
  exit 1
fi

echo "--> Applying sysctl tuning..."
cat > /etc/sysctl.d/99-nextcloud.conf <<'EOF'
# Redis background-save warning fix
vm.overcommit_memory = 1
# Larger connection backlog for the reverse proxy
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 4096
# File watchers/handles for large syncs
fs.inotify.max_user_watches = 524288
fs.file-max = 2097152
EOF
sysctl --system >/dev/null

echo "--> Raising container file limits (systemd docker drop-in)..."
if command -v systemctl >/dev/null && systemctl list-unit-files docker.service >/dev/null 2>&1; then
  mkdir -p /etc/systemd/system/docker.service.d
  cat > /etc/systemd/system/docker.service.d/limits.conf <<'EOF'
[Service]
LimitNOFILE=1048576
EOF
  systemctl daemon-reload
  systemctl restart docker || true
fi

echo "--> Opening firewall ports 80/443 (if a firewall manager is present)..."
if command -v ufw >/dev/null 2>&1; then
  ufw allow 80/tcp || true
  ufw allow 443/tcp || true
elif command -v firewall-cmd >/dev/null 2>&1; then
  firewall-cmd --permanent --add-service=http || true
  firewall-cmd --permanent --add-service=https || true
  firewall-cmd --reload || true
fi

echo "--> Checking container runtime..."
if command -v docker >/dev/null 2>&1; then
  docker version --format 'docker {{.Server.Version}} OK'
elif command -v podman >/dev/null 2>&1; then
  podman version --format 'podman {{.Version}} OK'
else
  echo "WARNING: neither docker nor podman found — install one before deploying." >&2
fi

echo "--> Host preparation complete."
