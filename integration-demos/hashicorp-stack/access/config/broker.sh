#!/bin/sh
# Bastion broker: start one socat TCP forwarder per authorized target. Shares
# the bastion tailscale node's network namespace, so it binds the tailnet
# interface — the workstation reaches these ports over the tunnel, and the
# broker forwards them (and ONLY them) to the internal targets.
#
#   BROKER_TARGETS="9200=boundary:9200,9202=boundary:9202"
#
# A target the workstation should NOT reach simply has no line here — there is
# no route to the internal network any other way.
set -eu

apk add --no-cache socat >/dev/null 2>&1 || true

IFS=','
for _t in ${BROKER_TARGETS:-}; do
    _listen="${_t%%=*}"
    _up="${_t#*=}"
    echo "broker: :$_listen -> $_up"
    socat TCP-LISTEN:"$_listen",fork,reuseaddr TCP:"$_up" &
done
unset IFS

# Reap and stay in the foreground.
trap 'kill 0' TERM INT
wait
