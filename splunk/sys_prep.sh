#!/bin/bash
# sys_prep.sh
# RW
# Prepares system for Splunk installation, aligning with Splunk installation manual.
# Run as root
# Usage: [NETWORK_INTERFACE=eth0] [SUBNET=10.0.77.0/24] ./sys_prep.sh

set -euo pipefail

# Configuration variables
NETWORK_INTERFACE="${NETWORK_INTERFACE:-eth0}"  # Default interface
SUBNET="${SUBNET:-10.0.77.0/24}"               # Allowed inbound network CIDR
SPLUNK_PORTS=("8000" "8088" "8089" "9997" "1514" "8191")  # Splunk ports
LOG_FILE="/var/log/splunk_sys_prep.log"
SYSCTL_FILE="/etc/sysctl.d/99-splunk.conf"

# Ensure script runs as root
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ This script must be run as root" >&2
    exit 1
fi

# Redirect output to log file and console
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

# Log function for consistent output
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error function for consistent error handling
error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2 | tee -a "$LOG_FILE"
    exit 1
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

add_system_user() {
    log "Creating splunk user and group"
    if getent group splunk >/dev/null; then
        log "Group splunk already exists"
    else
        groupadd -r -g 41812 splunk || error "Failed to create splunk group"
    fi
    if id splunk >/dev/null 2>&1; then
        log "User splunk already exists"
    else
        useradd --system -u 41812 -g splunk -s /bin/bash -m -d /home/splunk splunk || error "Failed to create splunk user"
    fi
    usermod -aG systemd-journal splunk || error "Failed to add splunk user to systemd-journal group"
}

install_firewalld() {
    log "Installing firewalld"
    if command_exists dnf; then
        dnf install -y firewalld firewall-config || error "Failed to install firewalld with dnf"
    elif command_exists apt; then
        apt update && apt install -y firewalld firewall-config || error "Failed to install firewalld with apt"
    else
        error "No supported package manager (dnf, apt) found"
    fi
}

configure_firewalld() {
    log "Configuring firewalld"
    systemctl is-active --quiet firewalld || {
        log "Starting and enabling firewalld"
        systemctl start firewalld.service || error "Failed to start firewalld"
        systemctl enable firewalld.service || error "Failed to enable firewalld"
    }

    # Validate network interface
    if ! ip link show "$NETWORK_INTERFACE" >/dev/null 2>&1; then
        error "Network interface $NETWORK_INTERFACE does not exist"

    # Create and configure splunk zone
    if ! firewall-cmd --get-zones | grep -q splunk; then
        firewall-cmd --permanent --new-zone=splunk || error "Failed to create splunk zone"
    fi
    firewall-cmd --permanent --zone=splunk --set-target=DROP || error "Failed to set DROP target for splunk zone"
    firewall-cmd --permanent --zone=splunk --change-interface="$NETWORK_INTERFACE" || error "Failed to assign interface $NETWORK_INTERFACE to splunk zone"

    # Add SSH rule to prevent lockout
    if ! firewall-cmd --zone=splunk --list-rich-rules | grep -q "port=22"; then
        firewall-cmd --permanent --zone=splunk --add-rich-rule="rule family=ipv4 source address=$SUBNET port port=22 protocol=tcp accept" || error "Failed to add SSH firewall rule"
    else
        log "SSH firewall rule already exists"
    fi

    # Add Splunk ports
    for port in "${SPLUNK_PORTS[@]}"; do
        if ! firewall-cmd --zone=splunk --list-rich-rules | grep -q "port=$port"; then
            firewall-cmd --permanent --zone=splunk --add-rich-rule="rule family=ipv4 source address=$SUBNET port port=$port protocol=tcp accept" || error "Failed to add firewall rule for port $port"
        else
            log "Firewall rule for port $port already exists"
        fi
    done

    firewall-cmd --reload || error "Failed to reload firewalld"
    log "Firewalld configured successfully"
}

configure_selinux() {
    if [ -f /etc/selinux/config ]; then
        SELINUX=$(grep ^SELINUX= /etc/selinux/config | cut -d= -f2)
        if [ "$SELINUX" != "disabled" ]; then
            log "Backing up SELinux config"
            cp /etc/selinux/config /etc/selinux/config.bak-$(date +%Y%m%d%H%M%S) || error "Failed to back up SELinux config"
            log "Setting SELinux to permissive mode (consider enforcing for production)"
            setenforce 0 || error "Failed to set SELinux to permissive"
            sed -i 's/^SELINUX=.*/SELINUX=permissive/' /etc/selinux/config || error "Failed to update SELinux config"
        else
            log "SELinux is already disabled"
        fi
        # Set SELinux context for Splunk directories (for enforcing mode)
        if command_exists semanage && command_exists restorecon; then
            log "Setting SELinux context for Splunk directories"
            semanage fcontext -a -t container_file_t "/home/splunk(/.*)?" || error "Failed to set SELinux fcontext"
            restorecon -R -v /home/splunk || error "Failed to restore SELinux context"
        else
            log "SELinux tools (semanage, restorecon) not found, skipping context configuration"
        fi
    else
        log "SELinux not detected on this system"
    fi
}

configure_sysctl() {
    log "Configuring sysctl parameters"
    log "Backing up sysctl config"
    cp /etc/sysctl.conf /etc/sysctl.conf.bak-$(date +%Y%m%d%H%M%S) || error "Failed to back up sysctl config"

    cat << EOF > "$SYSCTL_FILE"
$(grep -q "fs.file-max = 64000" "$SYSCTL_FILE" || echo "fs.file-max = 64000")
$(grep -q "vm.max_map_count = 262144" "$SYSCTL_FILE" || echo "vm.max_map_count = 262144")
$(grep -q "net.core.somaxconn = 1024" "$SYSCTL_FILE" || echo "net.core.somaxconn = 1024")
$(grep -q "net.ipv4.tcp_syncookies = 1" "$SYSCTL_FILE" || echo "net.ipv4.tcp_syncookies = 1")
$(grep -q "net.ipv4.tcp_tw_reuse = 1" "$SYSCTL_FILE" || echo "net.ipv4.tcp_tw_reuse = 1")
$(grep -q "net.ipv4.tcp_fin_timeout = 30" "$SYSCTL_FILE" || echo "net.ipv4.tcp_fin_timeout = 30")
$(grep -q "net.ipv4.tcp_keepalive_time = 1200" "$SYSCTL_FILE" || echo "net.ipv4.tcp_keepalive_time = 1200")
EOF
    sysctl --system || error "Failed to apply sysctl settings"
}

disable_thp_now() {
    log "Disabling Transparent Huge Pages (THP)"
    for file in /sys/kernel/mm/transparent_hugepage/{enabled,defrag}; do
        if [ -f "$file" ]; then
            echo never > "$file" || error "Failed to disable THP in $file"
        else
            log "THP file $file not found"
        fi
    done
}

disable_thp_service() {
    log "Creating systemd service to disable THP at boot"
    cat << EOF > /etc/systemd/system/disable-thp.service
[Unit]
Description=Disable Transparent Huge Pages (THP)
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c "echo 'never' > /sys/kernel/mm/transparent_hugepage/enabled && echo 'never' > /sys/kernel/mm/transparent_hugepage/defrag"
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload || error "Failed to reload systemd"
    systemctl enable disable-thp.service || error "Failed to enable disable-thp service"
    systemctl start disable-thp.service || error "Failed to start disable-thp service"
}

persist_file_limits() {
    log "Setting systemd user limits for Splunk"
    mkdir -p /etc/systemd/user.conf.d || error "Failed to create /etc/systemd/user.conf.d"
    cat << EOF > /etc/systemd/user.conf.d/splunk.conf
[Manager]
DefaultLimitFSIZE=infinity
DefaultLimitNOFILE=64000
DefaultLimitNPROC=20000
DefaultLimitDATA=6000000000
EOF
    systemctl daemon-reload || error "Failed to reload systemd"
}

check_settings() {
    log "Verifying system settings"
    [ "$(sysctl -n fs.file-max)" -ge 64000 ] || error "fs.file-max not set correctly"
    [ "$(sysctl -n vm.max_map_count)" -eq 262144 ] || error "vm.max_map_count not set correctly"
    [ "$(sysctl -n net.core.somaxconn)" -eq 1024 ] || error "net.core.somaxconn not set correctly"
    [ "$(cat /sys/kernel/mm/transparent_hugepage/enabled)" == "never" ] || error "THP enabled not set to never"
    [ "$(cat /sys/kernel/mm/transparent_hugepage/defrag)" == "never" ] || error "THP defrag not set to never"
    systemctl is-active --quiet disable-thp.service || error "disable-thp service not running"
    [ -f /etc/systemd/user.conf.d/splunk.conf ] || error "Systemd user limits not configured"
    log "All settings verified successfully"
}

execute() {
    add_system_user
    install_firewalld
    configure_firewalld
    configure_selinux
    configure_sysctl
    disable_thp_now
    disable_thp_service
    persist_file_limits
    check_settings
    log "System preparation for Splunk completed successfully"
}

execute