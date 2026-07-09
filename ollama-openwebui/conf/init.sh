#!/bin/bash

# Load environment variables
if [ -f ./.env ]; then
    source ./.env
else
    echo "Error: .env file not found"
    exit 1
fi

# Verify HOSTNAME is set
if [ -z "$HOSTNAME" ]; then
    HOSTNAME="open-webui.ai"
    echo "Warning: HOSTNAME not set in .env, using default: $HOSTNAME"
fi

# selinux GPU
setsebool container_use_devices=1

# System Configuration
cat > /etc/security/limits.d/openwebui.conf << EOF
*       soft    memlock    unlimited
*       hard    memlock    unlimited
EOF

# NVIDIA Configuration
cat > /etc/nvidia-container-runtime/config.toml << EOF
disable-require = false
[nvidia-container-cli]
environment = []
debug = "/var/log/nvidia-container-toolkit.log"
EOF

# Sysctl Configuration
cat > /etc/sysctl.d/99-openwebui.conf << EOF
# CPU et memory Performance
vm.swappiness=10
vm.dirty_ratio=60
vm.dirty_background_ratio=2
vm.vfs_cache_pressure=50

# Scheduling Optimization
kernel.sched_autogroup_enabled=0
kernel.sched_child_runs_first=1
kernel.sched_energy_aware=0
kernel.sched_rt_period_us=1000000
kernel.sched_rt_runtime_us=990000
kernel.sched_cfs_bandwidth_slice_us=3000

# Network Optimization
net.core.rmem_max=16777216
net.core.wmem_max=16777216
net.ipv4.tcp_rmem=4096 87380 16777216
net.ipv4.tcp_wmem=4096 65536 16777216
net.core.netdev_max_backlog=30000
net.ipv4.tcp_max_syn_backlog=8096
net.ipv4.tcp_max_tw_buckets=2000000
net.ipv4.tcp_tw_reuse=1
net.ipv4.tcp_fin_timeout=10

# Huge Pages
vm.nr_hugepages=8192
EOF

# Local hosts configuration
if ! grep -q "$HOSTNAME" /etc/hosts; then
    echo "127.0.0.1 $HOSTNAME" >> /etc/hosts
fi

# nvidia toolkit, podman
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sed -i -e '/experimental/ s/^#//g' /etc/apt/sources.list.d/nvidia-container-toolkit.list

apt-get update

apt-get install -y \
    linux-headers-$(uname -r) \
    podman \
    podman-compose \
    curl \
    nvidia-driver \
    nvidia-cuda-toolkit \
    nvidia-container-toolkit \
    nvidia-kernel-dkms

# Apply sysctl settings
sysctl -p /etc/sysctl.d/99-openwebui.conf

# Set/Check NVIDIA configuration
nvidia-ctk cdi generate --output=/var/run/cdi/nvidia.yaml
nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
chmod a+r /var/run/cdi/nvidia.yaml /var/run/cdi/nvidia.yaml
nvidia-smi -L
nvidia-ctk cdi list
nvidia-container-cli info