#!/bin/sh

# Run this in the splunk host as root

if ! (set -o pipefail 2>/dev/null); then
  # dash does not support pipefail
  set -efx
else
  set -efx -o pipefail
fi

# bash does not expand alias by default for non-interactive script
if [ -n "$BASH_VERSION" ]; then
  shopt -s expand_aliases
fi

alias cp="cp -f"
alias mkdir="mkdir -p"

SPLUNK_HOME="/opt/splunk"
SPLUNK_USER="splunk"

. "/etc/os-release"
DISTRO="$ID"
DISTRO_BASE="$ID_LIKE"
IS_DEBIAN_BASE=$(printf "$DISTRO_BASE" | grep "debian" || [ $? = 1 ])
IS_UBUNTU_BASE=$(printf "$DISTRO_BASE" | grep "ubuntu" || [ $? = 1 ])

# Create "splunk" user without password and shell
# Splunk app can still run shell scripts even without shell
if ! id -u "$SPLUNK_USER" >/dev/null 2>&1; then
  echo "\"$SPLUNK_USER\" user not found, creating..."
  useradd --system --create-home --home-dir "$SPLUNK_HOME" --shell "/usr/sbin/nologin" "$SPLUNK_USER"
else
  echo "\"$SPLUNK_USER\" user exists"
fi

# Grant access to /var/log
if [ "$DISTRO" = "debian" ] || [ -n "$IS_DEBIAN_BASE" ] || [ -n "$IS_UBUNTU_BASE" ]; then
  usermod --append --groups "adm" "$SPLUNK_USER"
fi

tar xzf splunk-*-linux-amd64.tgz -C "/opt"

SPLUNK_ETC="$SPLUNK_HOME/etc"
SPLUNK_SYSTEM="$SPLUNK_ETC/system/local"
SPLUNK_CERTS="$SPLUNK_ETC/auth/mycerts"
SPLUNK_APPS="$SPLUNK_ETC/apps"
SPLUNK_DEPLOY_APPS="$SPLUNK_ETC/deployment-apps"

CA_PATH="/etc/ssl/certs/ca-certificates.crt"
if [ -f "/etc/ssl/certs/ca-bundle.crt" ]; then
  CA_PATH="/etc/ssl/certs/ca-bundle.crt"
fi

cd "splunk/"

cp "splunk-launch.conf" "$SPLUNK_ETC/splunk-launch.conf"
mkdir "$SPLUNK_SYSTEM"
cp "alert_actions.conf" "$SPLUNK_SYSTEM/alert_actions.conf"
cp "authentication.conf" "$SPLUNK_SYSTEM/authentication.conf"
cp "authorize.conf" "$SPLUNK_SYSTEM/authorize.conf"
cp "health.conf" "$SPLUNK_SYSTEM/health.conf"
cp "inputs.conf" "$SPLUNK_SYSTEM/inputs.conf"
cp "limits.conf" "$SPLUNK_SYSTEM/limits.conf"
cp "server.conf" "$SPLUNK_SYSTEM/server.conf"
cp "user-seed.conf" "$SPLUNK_SYSTEM/user-seed.conf"
cp "web.conf" "$SPLUNK_SYSTEM/web.conf"

stty -echo
read -p 'Server private key password (input will not be displayed): ' SSL_PASSWORD
stty echo
echo

sed -i "s/^sslPassword\s*=..*/sslPassword = $SSL_PASSWORD/" "$SPLUNK_SYSTEM/inputs.conf"
chmod 600 "$SPLUNK_SYSTEM/inputs.conf"
sed -i "s/^sslPassword\s*=..*/sslPassword = $SSL_PASSWORD/" "$SPLUNK_SYSTEM/server.conf"
sed -i "s/^sslRootCAPath\s*=..*/sslRootCAPath = $CA_PATH/" "$SPLUNK_SYSTEM/server.conf"
chmod 600 "$SPLUNK_SYSTEM/server.conf"
sed -i "s/^sslPassword\s*=..*/sslPassword = $SSL_PASSWORD/" "$SPLUNK_SYSTEM/web.conf"
chmod 600 "$SPLUNK_SYSTEM/web.conf"

cd "../"
tar xzf "100_splunkcloud.tar.gz" -C "$SPLUNK_APPS"

# optional: customise login background
# see splunk/web.conf
APPSERVER="$SPLUNK_APPS/search/appserver/static"
mkdir "$APPSERVER/customfavicon"
cp "favicon.ico" "$APPSERVER/customfavicon/"
mkdir "$APPSERVER/logincustomlogo"
cp "logo.png" "$APPSERVER/logincustomlogo"
mkdir "$APPSERVER/logincustombg"
cp "background.png" "$APPSERVER/logincustombg/img.png"
mkdir "$APPSERVER/pdfcustomlogo"
cp "pdf-logo.jpg" "$APPSERVER/pdfcustomlogo/logo.jpg"

cd "../certs/"

mkdir "$SPLUNK_CERTS"
cp "splunk-cert.pem" "$SPLUNK_CERTS/splunk-cert.pem"
cp "splunk-cert.key" "$SPLUNK_CERTS/splunk-cert.key"
cp "splunk-cert-web.pem" "$SPLUNK_CERTS/splunk-cert-web.pem"
find "$SPLUNK_CERTS" -type f | xargs chmod 400

# optional: SAML SSO
mkdir "$SPLUNK_ETC/etc/auth/idpCerts"
cp "idpCert.pem" "$SPLUNK_ETC/etc/auth/idpCerts/idpCert.pem"

# Deployment apps
cd "../"

mkdir "$SPLUNK_DEPLOY_APPS"
tar xzf "1-deploymentserver.tar.gz" -C "$SPLUNK_DEPLOY_APPS"
tar xzf "1-indexserver.tar.gz" -C "$SPLUNK_DEPLOY_APPS"
tar xzf "100_splunkcloud.tar.gz" -C "$SPLUNK_DEPLOY_APPS"
# client cert
cp "certs/splunkcloud_client.pem" "$SPLUNK_DEPLOY_APPS/100_splunkcloud/default/splunkcloud_client.pem"

# forward logs to heavy forwarder
stty -echo
read -p '1-indexserver private key password (input will not be displayed): ' SSL_PASSWORD
stty echo
echo

sed -i "s/^sslPassword\s*=..*/sslPassword = $SSL_PASSWORD/" "$SPLUNK_DEPLOY_APPS/1-indexserver/local/outputs.conf"

SSL_PASSWORD=""

# forward logs to splunk cloud
stty -echo
read -p '100_splunkcloud private key password (input will not be displayed): ' SSL_PASSWORD
stty echo
echo

sed -i "s/^sslPassword\s*=..*/sslPassword = $SSL_PASSWORD/" "$SPLUNK_APPS/100_splunkcloud/local/outputs.conf"
sed -i "s/^sslPassword\s*=..*/sslPassword = $SSL_PASSWORD/" "$SPLUNK_DEPLOY_APPS/100_splunkcloud/local/outputs.conf"

SSL_PASSWORD=""

# Use the latest cert store
cp "$CA_PATH" "$SPLUNK_APPS/100_splunkcloud/local/ca-certificates.crt"
cp "$CA_PATH" "$SPLUNK_DEPLOY_APPS/100_splunkcloud/local/ca-certificates.crt"
cp "$CA_PATH" "$SPLUNK_DEPLOY_APPS/1-deploymentserver/local/ca-certificates.crt"
cp "$CA_PATH" "$SPLUNK_DEPLOY_APPS/1-indexserver/local/ca-certificates.crt"

chown -R "$SPLUNK_USER":"$SPLUNK_USER" "$SPLUNK_HOME"

# Required by cpu_metric.sh & vmstat_metric.sh of Splunk_TA_nix
if [ "$DISTRO" = "debian" ] || [ -n "$IS_DEBIAN_BASE" ]; then
  apt install -y --no-upgrade "sysstat"
elif [ "$DISTRO" = "fedora" ] || [ -n "$IS_FEDORA_BASE" ]; then
  dnf install --refresh -y "sysstat"
elif [ -n "$IS_SUSE_BASE" ]; then
  zypper install -y "sysstat"
elif [ "$DISTRO" = "photon" ]; then
  tdnf install --refresh -y "sysstat"
fi

cp "splunkd.service" "/etc/systemd/system/splunkd.service"

# "Executable path is not absolute" error
# this error is fixed in Ubuntu 20.04
# it's probably fixed in prior to systemd 245, but definitely after systemd 237 (Ubuntu 18.04)
if [ $(systemctl --version | grep -oP 'systemd\s\K\d+') -lt "245" ]; then
  sed -E -i 's|([+-])chown|\1/bin/chown|g' "/etc/systemd/system/splunkd.service"
fi

# cgroup1
if [ -d "/sys/fs/cgroup/unified/" ]; then
  sed -i 's|cgroup/system.slice|cgroup/unified/system.slice|' "/etc/systemd/system/splunkd.service"
elif [ -d "/sys/fs/cgroup/systemd/" ]; then
  sed -i 's|cgroup/system.slice|cgroup/systemd/system.slice|' "/etc/systemd/system/splunkd.service"
fi

systemctl daemon-reload

read -p 'Start/restart splunk? (y/n): ' RESTART_SPLUNK

if [ "$RESTART_SPLUNK" = "y" ]; then
  echo "Start/restarting splunk..."
  IS_ENABLED=$(systemctl is-enabled "splunkd.service" || [ $? = 1 ])
  if [ "$IS_ENABLED" != "enabled" ]; then
    systemctl enable --now "splunkd.service"
  else
    systemctl restart "splunkd.service"
  fi
fi
