#!/usr/bin/env bash
# Prepare a VM for its portal-stack role. Idempotent; run as root.
#
#   ./prep-host.sh <mesh|data|scm|secrets|identity|access|portal>
#
# Installs podman, loads required kernel modules, applies the common +
# role-specific sysctl profile, raises file limits, creates the config
# tree, and prints the firewall openings the role needs (it does not touch
# your firewall).
set -euo pipefail

ROLE=${1:?usage: prep-host.sh <mesh|data|scm|secrets|identity|access|portal>}
HERE=$(cd "$(dirname "$0")" && pwd)

case "$ROLE" in
  mesh|data|scm|secrets|identity|access|portal) ;;
  *) echo "unknown role: $ROLE"; exit 1 ;;
esac

echo "==> podman"
if ! command -v podman >/dev/null; then
  if command -v dnf >/dev/null; then dnf install -y podman
  elif command -v apt-get >/dev/null; then apt-get update -q && apt-get install -y podman
  else echo "FAIL: no dnf/apt — install podman >= 4.9 manually"; exit 1
  fi
fi
podman --version

echo "==> kernel modules"
MODULES="br_netfilter"
[ "$ROLE" = "access" ] && MODULES="$MODULES nf_conntrack"
for m in $MODULES; do modprobe "$m"; done
printf '%s\n' $MODULES > /etc/modules-load.d/portal-stack.conf

echo "==> sysctl profile (common + $ROLE)"
install -m 0644 "$HERE/sysctl.d/00-portal-common.conf" /etc/sysctl.d/
if [ -f "$HERE/sysctl.d/10-$ROLE.conf" ]; then
  install -m 0644 "$HERE/sysctl.d/10-$ROLE.conf" /etc/sysctl.d/
fi
sysctl --system >/dev/null
echo "    applied"

echo "==> file limits"
cat > /etc/security/limits.d/portal-stack.conf <<'EOF'
* soft nofile 262144
* hard nofile 262144
EOF

echo "==> config tree"
mkdir -p /etc/backstage-portal/tls
chmod 750 /etc/backstage-portal /etc/backstage-portal/tls

if [ "$ROLE" = "secrets" ]; then
  if [ -n "$(swapon --show --noheadings 2>/dev/null)" ]; then
    echo "WARNING: swap is active on a Vault host. Run 'swapoff -a' and remove"
    echo "         swap entries from /etc/fstab so unsealed key material can"
    echo "         never be paged to disk."
  fi
fi

echo "==> firewall openings required for role '$ROLE' (apply via your firewall):"
case "$ROLE" in
  mesh)     echo "    8501/tcp (HTTPS API+UI), 8502/tcp (gRPC TLS), 8301/tcp+udp (gossip), 8300/tcp (server RPC)" ;;
  data)     echo "    5432/tcp (Postgres TLS; restrict to portal, secrets, identity, access hosts)" ;;
  scm)      echo "    3000/tcp (Gitea HTTPS; restrict to portal host + admin network)" ;;
  secrets)  echo "    8200/tcp (Vault HTTPS; restrict to stack hosts + admin network)" ;;
  identity) echo "    8443/tcp (Keycloak HTTPS; public for browser SSO)" ;;
  access)   echo "    9200/tcp (API TLS), 9202/tcp (worker proxy — the ONLY end-user entry), 9203/tcp (ops, restrict to monitoring)" ;;
  portal)   echo "    8443/tcp (nginx TLS; restrict to access host ONLY — end users come through Boundary)" ;;
esac

echo "prep-host: DONE ($ROLE)"
