#!/usr/bin/env bash
# Prepare a Linux host to run production OpenSearch containers: raise
# vm.max_map_count, disable swap pressure, allow memory locking and enough file
# handles, and turn off transparent hugepages. Run with sudo.
#
#   sudo bash prepare-host.sh            apply (snapshots current values first)
#   sudo bash prepare-host.sh --check    show current vs required
#   sudo bash prepare-host.sh --revert   restore the snapshot
set -euo pipefail

SNAPSHOT=/var/lib/opensearch-host-prep.snapshot
REQ_MAX_MAP=262144
REQ_SWAPPINESS=1
LIMITS_FILE=/etc/security/limits.d/opensearch.conf
THP_UNIT=/etc/systemd/system/disable-thp.service

need_root() { [ "$(id -u)" -eq 0 ] || { echo "run as root (sudo)"; exit 1; }; }

current_thp() { cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null | sed 's/.*\[\(.*\)\].*/\1/'; }

do_check() {
  echo "vm.max_map_count : $(sysctl -n vm.max_map_count)  (require >= ${REQ_MAX_MAP})"
  echo "vm.swappiness    : $(sysctl -n vm.swappiness)  (require ${REQ_SWAPPINESS})"
  echo "THP enabled      : $(current_thp)  (require never)"
  echo "memlock limit    : $(grep -h memlock ${LIMITS_FILE} 2>/dev/null || echo 'not set')"
}

do_apply() {
  need_root
  if [ ! -f "${SNAPSHOT}" ]; then
    {
      echo "ORIG_MAX_MAP=$(sysctl -n vm.max_map_count)"
      echo "ORIG_SWAPPINESS=$(sysctl -n vm.swappiness)"
      echo "ORIG_THP=$(current_thp)"
    } > "${SNAPSHOT}"
  fi

  sysctl -w vm.max_map_count=${REQ_MAX_MAP}
  sysctl -w vm.swappiness=${REQ_SWAPPINESS}
  cat > /etc/sysctl.d/99-opensearch.conf <<EOF
vm.max_map_count=${REQ_MAX_MAP}
vm.swappiness=${REQ_SWAPPINESS}
EOF

  cat > "${LIMITS_FILE}" <<EOF
* soft memlock unlimited
* hard memlock unlimited
* soft nofile 65536
* hard nofile 65536
EOF

  cat > "${THP_UNIT}" <<EOF
[Unit]
Description=Disable Transparent Huge Pages for OpenSearch
After=sysinit.target local-fs.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/enabled'

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now disable-thp.service
  echo "Host prepared. Log out/in for limits.d to take effect on new sessions."
}

do_revert() {
  need_root
  [ -f "${SNAPSHOT}" ] || { echo "no snapshot at ${SNAPSHOT}"; exit 1; }
  # shellcheck disable=SC1090
  . "${SNAPSHOT}"
  sysctl -w vm.max_map_count="${ORIG_MAX_MAP}"
  sysctl -w vm.swappiness="${ORIG_SWAPPINESS}"
  rm -f /etc/sysctl.d/99-opensearch.conf "${LIMITS_FILE}"
  systemctl disable --now disable-thp.service 2>/dev/null || true
  rm -f "${THP_UNIT}"
  systemctl daemon-reload
  echo never > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
  [ -n "${ORIG_THP:-}" ] && echo "${ORIG_THP}" > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
  rm -f "${SNAPSHOT}"
  echo "Reverted host tuning."
}

case "${1:-apply}" in
  --check) do_check ;;
  --revert) do_revert ;;
  *) do_apply ;;
esac
