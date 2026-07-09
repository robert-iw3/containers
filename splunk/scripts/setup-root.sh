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
alias rm="rm -rf"

. "/etc/os-release"
DISTRO="$ID"
DISTRO_BASE="$ID_LIKE"
IS_DEBIAN_BASE=$(printf "$DISTRO_BASE" | grep "debian" || [ $? = 1 ])
IS_UBUNTU_BASE=$(printf "$DISTRO_BASE" | grep "ubuntu" || [ $? = 1 ])
IS_FEDORA_BASE=$(printf "$DISTRO_BASE" | grep "fedora" || [ $? = 1 ])
IS_SUSE_BASE=$(printf "$DISTRO_BASE" | grep "suse" || [ $? = 1 ])

cp "hosts" "/etc/hosts"
# prefer shortname
hostnamectl set-hostname splunkhostname --static

# optional: use static host key
# `HostKey /etc/ssh/splunk_host_ed25519_key` must be set in sshd_config
cp "splunk_host_ed25519_key" "/etc/ssh/splunk_host_ed25519_key"
chmod 600 "/etc/ssh/splunk_host_ed25519_key"
cp "splunk_host_ed25519_key.pub" "/etc/ssh/splunk_host_ed25519_key.pub"
chmod 644 "/etc/ssh/splunk_host_ed25519_key.pub"
chown -R root:root "/etc/ssh/"

mkdir "/etc/ssh/sshd_config.d/"
rm "/etc/ssh/sshd_config.d/50-cloud-init.conf"
cp "sshd_config" "/etc/ssh/splunk_host_ed25519_key"
echo "Installed SSH host key"

if [ "$DISTRO" = "debian" ] || [ -n "$IS_DEBIAN_BASE" ] || [ -n "$IS_UBUNTU_BASE" ]; then
  CERT_PATH="/usr/local/share/ca-certificates"
  UPDATE_CERT="update-ca-certificates"
elif [ "$DISTRO" = "fedora" ] || [ -n "$IS_FEDORA_BASE" ]; then
  CERT_PATH="/usr/share/pki/ca-trust-source/anchors"
  UPDATE_CERT="update-ca-trust"
elif [ -n "$IS_SUSE_BASE" ]; then
  # https://github.com/openSUSE/ca-certificates
  CERT_PATH="/usr/share/pki/trust/anchors"
  UPDATE_CERT="update-ca-certificates"
fi
mkdir "$CERT_PATH"
# Enterprise root CA
cp "enterprise_root_cacert.crt" "$CERT_PATH/enterprise_cacert.crt"
cp "enterprise_intermediate_cacert.crt" "$CERT_PATH/enterprise_intermediate_cacert.crt"
# Splunk Cloud root CA
cp "100_splunkcloud_root_cacert.crt" "$CERT_PATH/100_splunkcloud_root_cacert.crt"
cp "100_splunkcloud_intermediate_cacert.crt" "$CERT_PATH/100_splunkcloud_intermediate_cacert.crt"
# UF CA
cp "splunkuf-ca.crt" "$CERT_PATH/splunkuf-ca.crt"
$UPDATE_CERT
echo "Installed custom CA certs"

# https://docs.splunk.com/Documentation/Splunk/latest/Installation/InstallonLinux#Information_on_expected_default_shell_and_caveats_for_Debian_shells
# https://unix.stackexchange.com/a/442518
IS_BASH=$(readlink -f "/bin/sh" | grep "bash" || [ $? = 1 ])
if [ -z "$IS_BASH" ]; then
  ln -sf bash "/bin/sh.bash"
  mv "/bin/sh.bash" "/bin/sh"
  echo "Switched default shell to bash"
fi
