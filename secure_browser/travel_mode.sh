#!/usr/bin/env bash
# OPT-IN host-side discovery hardening for public wifi. The container keeps the
# browser contained, but the HOST is what joins the hotel network — and it announces
# itself at layers the container never touches: its real MAC address, its hostname in
# DHCP requests, and mDNS/LLMNR name broadcasts. This script turns those off for the
# currently-active wifi connection profile, and can revert them.
#
#   ./travel_mode.sh on       randomize MAC, stop sending hostname, silence mDNS/LLMNR
#                             (reconnects the wifi to apply — expect a brief drop)
#   ./travel_mode.sh off      revert the profile to NetworkManager defaults
#   ./travel_mode.sh status   show the current settings
#
# Scope: modifies ONLY the active wifi connection profile via nmcli. Nothing else on
# the host is touched. Run 'off' when back on a trusted network if you want the
# stable MAC back (e.g. for DHCP reservations).
set -euo pipefail

wifi_dev() {
    for d in /sys/class/net/*/wireless; do
        [ -e "$d" ] || continue
        basename "$(dirname "$d")"
        return 0
    done
    echo "ERROR: no wireless adapter on this machine" >&2
    return 1
}

DEV=$(wifi_dev)
CON=$(nmcli -g GENERAL.CONNECTION device show "$DEV")
if [ -z "$CON" ]; then
    echo "ERROR: wifi adapter ${DEV} has no active connection — join the network first" >&2
    exit 1
fi
echo "[travel] wifi: ${DEV}, connection profile: ${CON}"

case "${1:-status}" in
    on)
        nmcli connection modify "$CON" \
            802-11-wireless.cloned-mac-address random \
            ipv4.dhcp-send-hostname no \
            ipv6.dhcp-send-hostname no \
            connection.mdns 0 \
            connection.llmnr 0
        echo "[travel] applying (wifi will reconnect)..."
        nmcli connection up "$CON" >/dev/null
        echo "[travel] ON — randomized MAC, no hostname in DHCP, mDNS/LLMNR silenced"
        ;;
    off)
        nmcli connection modify "$CON" \
            802-11-wireless.cloned-mac-address "" \
            ipv4.dhcp-send-hostname yes \
            ipv6.dhcp-send-hostname yes \
            connection.mdns -1 \
            connection.llmnr -1
        echo "[travel] applying (wifi will reconnect)..."
        nmcli connection up "$CON" >/dev/null
        echo "[travel] OFF — profile back to NetworkManager defaults"
        ;;
    status)
        nmcli -f 802-11-wireless.cloned-mac-address,ipv4.dhcp-send-hostname,ipv6.dhcp-send-hostname,connection.mdns,connection.llmnr \
            connection show "$CON"
        ip link show "$DEV" | awk '/link\/ether/{print "current MAC: " $2}'
        ;;
    *)
        echo "usage: $0 {on|off|status}" >&2
        exit 2
        ;;
esac
