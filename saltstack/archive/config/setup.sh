#!/usr/bin/env bash

set -o errexit
set -o pipefail

# shellcheck source=config/setup-funcs.sh
FUNCTIONS_FILE="${SALT_RUNTIME_DIR}/setup-funcs.sh"
source "${FUNCTIONS_FILE}"

log_info "Adding salt repository..."
add_salt_repository

# Configure ssh
log_info "Configuring ssh ..."
sed -i -e "s|^[# ]*StrictHostKeyChecking.*$|    StrictHostKeyChecking no|" /etc/ssh/ssh_config
{
  echo "    UserKnownHostsFile /dev/null"
  echo "    LogLevel ERROR"
  echo "#   IdentityFile salt_ssh_key"
} >> /etc/ssh/ssh_config

SUPERVISOR_CONFIG_FILE=/etc/supervisor/supervisord.conf

# Configure logrotate
log_info "Configuring logrotate ..."

# move supervisord.log file to ${SALT_LOGS_DIR}/supervisor/
sed -i "s|^[#]*logfile=.*|logfile=${SALT_LOGS_DIR}/supervisor/supervisord.log ;|" "${SUPERVISOR_CONFIG_FILE}"

# fix "unknown group 'syslog'" error preventing logrotate from functioning
sed -i "s|^su root syslog$|su root root|" /etc/logrotate.conf

# Configure supervisor
log_info "Configuring supervisor ..."

# run supervisord as root
if grep -E "^user=" "${SUPERVISOR_CONFIG_FILE}"; then
  sed -i "s|^user=.*|user=root|" "${SUPERVISOR_CONFIG_FILE}"
else
  sed -i "s|^\[supervisord\]\$|[supervisord]\nuser=root|" "${SUPERVISOR_CONFIG_FILE}"
fi

# configure supervisord to start salt-master
cat > /etc/supervisor/conf.d/salt-master.conf <<EOF
[program:salt-master]
priority=5
directory=/home/salt
environment=HOME=/home/salt
command=/usr/bin/salt-master
user=salt
autostart=true
autorestart=true
stopsignal=TERM
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
EOF

# configure supervisord to start crond
cat > /etc/supervisor/conf.d/cron.conf <<EOF
[program:cron]
priority=20
directory=/tmp
command=/usr/sbin/cron -f
user=root
autostart=true
autorestart=true
stdout_logfile=${SALT_LOGS_DIR}/supervisor/%(program_name)s.log
stderr_logfile=${SALT_LOGS_DIR}/supervisor/%(program_name)s.log
EOF
