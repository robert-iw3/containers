#!/bin/sh

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

. "/etc/os-release"
DISTRO="$ID"
DISTRO_BASE="$ID_LIKE"
IS_DEBIAN_BASE=$(printf "$DISTRO_BASE" | grep "debian" || [ $? = 1 ])
IS_FEDORA_BASE=$(printf "$DISTRO_BASE" | grep "fedora" || [ $? = 1 ])
IS_SUSE_BASE=$(printf "$DISTRO_BASE" | grep "suse" || [ $? = 1 ])

SSSD="sssd-ad sssd-tools realmd adcli"
if [ "$DISTRO" = "debian" ] || [ -n "$IS_DEBIAN_BASE" ]; then
  apt install -y --no-upgrade $SSSD
elif [ "$DISTRO" = "fedora" ] || [ -n "$IS_FEDORA_BASE" ]; then
  dnf install --refresh -y $SSSD
elif [ -n "$IS_SUSE_BASE" ]; then
  zypper install -y $SSSD
fi

mkdir "/etc/sudoers.d/"
cp "sudoers" "/etc/sudoers.d/ad_group"
echo 'Installed "/etc/sudoers.d/ad_group"'

read -p 'Domain Admin username including @DOMAIN.EXAMPLE in uppercase (enter "n" to skip): ' domain_admin
if [ -n "$domain_admin" ] && [ "$domain_admin" != "n" ]; then
  realm join -v "domain.example" -U "$domain_admin"
  echo "Joined Example AD domain"
fi

mkdir "/etc/sssd"
cp "sssd.conf" "/etc/sssd/sssd.conf"
systemctl restart sssd.service
echo 'Installed "/etc/sssd/sssd.conf"'

# https://serverfault.com.stackexchange.com/questions/725547/unable-to-create-home-directory-for-ldap-login
if ([ "$DISTRO" = "debian" ] || [ -n "$IS_DEBIAN_BASE" ]) && [ -z $(cat "/etc/pam.d/common-session" | grep "pam_mkhomedir" || [ $? = 1 ])]; then
  echo "In the next screen, ensure 'Create home directory on login' is selected".
  sleep 10
  pam-auth-update
fi
