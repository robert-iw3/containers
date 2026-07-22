#!/bin/sh
# Bring up a kernel WireGuard interface from a mounted config, then stay in the
# foreground. Used by both the compose stack and the Quadlet deployment.
#
# Env:
#   WG_ADDRESS   tunnel address to assign, e.g. 10.9.0.1/24   (required)
#   WG_CONF      wg config path (default /etc/wireguard/wg0.conf)
#   WG_ROUTES    extra CIDRs to route via wg0 (space separated, optional)
#   SERVE_DIR    if set, serve this dir over HTTP on the tunnel address:80
#
# Requires the host `wireguard` kernel module (the deploy/UAT ensures it) and
# CAP_NET_ADMIN.
set -eu

WG_CONF="${WG_CONF:-/etc/wireguard/wg0.conf}"

ip link add wg0 type wireguard
wg setconf wg0 "$WG_CONF"
ip address add "$WG_ADDRESS" dev wg0
ip link set wg0 up

for _r in ${WG_ROUTES:-}; do
    ip route replace "$_r" dev wg0
done

if [ -n "${SERVE_DIR:-}" ]; then
    _addr="${WG_ADDRESS%%/*}"
    busybox-extras httpd -f -p "${_addr}:80" -h "$SERVE_DIR" &
fi

echo "wg0 up: $WG_ADDRESS"
wg show wg0

# Tear the interface down cleanly on stop.
trap 'ip link del wg0 2>/dev/null || true; exit 0' TERM INT QUIT
while :; do sleep 3600 & wait $!; done
