#!/usr/bin/env bash
# Prepare a host BEFORE running containerized Elasticsearch / Kibana. Applies the
# kernel + limits tuning Elasticsearch needs to start and perform, balancing security
# with performance. Idempotent; run with sudo on each ES/Kibana host.
#
#   sudo ./prepare-host.sh            # apply + persist
#   sudo ./prepare-host.sh --check    # report current vs required, change nothing
#
# Why each setting (Elastic's own production guidance):
#   vm.max_map_count=262144  ES uses mmap; below this the bootstrap check FAILS and
#                            the node refuses to start (or restart-loops, burning CPU).
#   vm.swappiness=1          Keep the JVM heap in RAM; swapping heap wrecks latency.
#   memlock=unlimited        So bootstrap.memory_lock=true can pin the heap.
#   nofile=65536, nproc=4096 ES opens many shards/segments/connections.
#   THP=never (or madvise)   Transparent Huge Pages cause GC latency spikes for the JVM.
set -euo pipefail

REQ_MAX_MAP=262144
REQ_SWAPPINESS=1
REQ_NOFILE=65536
REQ_NPROC=4096
SNAP="/var/lib/elastic-host-prep.snapshot"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

# --revert: restore the values captured at apply time, then remove the persisted config.
if [ "${1:-}" = "--revert" ]; then
  [ "$(id -u)" = 0 ] || { echo "run with sudo to revert"; exit 1; }
  [ -f "$SNAP" ] || { echo "no snapshot at $SNAP; nothing to revert"; exit 1; }
  . "$SNAP"
  sysctl -w vm.max_map_count="$ORIG_MAX_MAP" vm.swappiness="$ORIG_SWAPPINESS" >/dev/null
  echo "$ORIG_THP" > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
  rm -f /etc/sysctl.d/99-elasticsearch.conf /etc/security/limits.d/99-elasticsearch.conf
  systemctl disable --now disable-thp.service 2>/dev/null || true
  rm -f /etc/systemd/system/disable-thp.service "$SNAP"
  echo "reverted host to: max_map_count=$ORIG_MAX_MAP swappiness=$ORIG_SWAPPINESS thp=$ORIG_THP"
  exit 0
fi

status() { printf "  %-22s current=%-10s required=%s\n" "$1" "$2" "$3"; }

echo "== host readiness for Elasticsearch =="
status "vm.max_map_count" "$(cat /proc/sys/vm/max_map_count)" ">= $REQ_MAX_MAP"
status "vm.swappiness"    "$(cat /proc/sys/vm/swappiness)"    "$REQ_SWAPPINESS"
status "THP"              "$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null | grep -oE '\[[a-z]+\]' || echo n/a)" "[never] or [madvise]"

if [ "$CHECK_ONLY" = 1 ]; then
  echo "(--check: no changes made)"; exit 0
fi

[ "$(id -u)" = 0 ] || { echo "run with sudo to apply changes"; exit 1; }

# Snapshot current values once, so --revert can restore this host exactly.
if [ ! -f "$SNAP" ]; then
  mkdir -p "$(dirname "$SNAP")"
  cat > "$SNAP" <<EOF
ORIG_MAX_MAP=$(cat /proc/sys/vm/max_map_count)
ORIG_SWAPPINESS=$(cat /proc/sys/vm/swappiness)
ORIG_THP=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null | grep -oE '\[[a-z]+\]' | tr -d '[]' || echo madvise)
EOF
fi

echo "== applying =="
# 1. sysctl (persisted)
cat > /etc/sysctl.d/99-elasticsearch.conf <<EOF
vm.max_map_count = $REQ_MAX_MAP
vm.swappiness = $REQ_SWAPPINESS
EOF
sysctl -p /etc/sysctl.d/99-elasticsearch.conf

# 2. ulimits (persisted) for the container runtime / elasticsearch user
cat > /etc/security/limits.d/99-elasticsearch.conf <<EOF
*    soft    nofile    $REQ_NOFILE
*    hard    nofile    $REQ_NOFILE
*    soft    nproc     $REQ_NPROC
*    hard    nproc     $REQ_NPROC
*    soft    memlock   unlimited
*    hard    memlock   unlimited
EOF

# 3. disable swap (ES strongly prefers no swap; comment out if you must keep swap)
swapoff -a || true
sed -i.bak '/\bswap\b/s/^/#/' /etc/fstab || true

# 4. disable Transparent Huge Pages at boot (best-effort systemd unit)
cat > /etc/systemd/system/disable-thp.service <<'EOF'
[Unit]
Description=Disable Transparent Huge Pages (for Elasticsearch)
After=sysinit.target
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/enabled'
[Install]
WantedBy=basic.target
EOF
echo never > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
systemctl daemon-reload && systemctl enable --now disable-thp.service 2>/dev/null || true

echo "== done. re-run with --check to verify. =="
