#!/bin/sh
# Workstation-side forwarder. Shares the endpoint tailscale node's netns and
# exposes the bastion's brokered ports on localhost, dialed through the node's
# SOCKS5 proxy (tailnet destinations live in tailscaled's userspace netstack, so
# a plain TCP dial can't reach them — SOCKS5 is the bridge).
#
#   psql -h 127.0.0.1 -p 9200 ...   ->  SOCKS5 :1055  ->  tunnel  ->  bastion:9200
#
#   SOCKS_ADDR=127.0.0.1:1055
#   BASTION_HOST=<bastion tailnet ip or magicDNS name>
#   FORWARD_PORTS="9200 9202"
set -eu

apk add --no-cache socat >/dev/null 2>&1 || true

: "${SOCKS_HOST:=127.0.0.1}"
: "${SOCKS_PORT:=1055}"
: "${BASTION_HOST:?set BASTION_HOST to the bastion tailnet address}"

for _p in ${FORWARD_PORTS:-9200}; do
    echo "forward: :$_p -> $BASTION_HOST:$_p (via SOCKS5 $SOCKS_HOST:$SOCKS_PORT)"
    # Bind all interfaces inside this isolated netns; the compose publish maps
    # the workstation's 127.0.0.1:<port> to it.
    # SOCKS5-CONNECT:<socks-server>:<socks-port>:<target-host>:<target-port>
    socat TCP-LISTEN:"$_p",fork,reuseaddr \
        SOCKS5-CONNECT:"$SOCKS_HOST":"$SOCKS_PORT":"$BASTION_HOST":"$_p" &
done

trap 'kill 0' TERM INT
wait
