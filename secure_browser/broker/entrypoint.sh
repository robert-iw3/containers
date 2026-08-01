#!/bin/sh
# Broker entrypoint. Order matters: tunnel first (fail closed), then filtered DNS,
# then the SOCKS5 choke point — the "ready" line is printed only when the whole
# chain is serving, and run.sh waits for it.
set -eu

INT_IP="${SB_INT_IP:?SB_INT_IP not set}"
INT_SUBNET="${SB_INT_SUBNET:-172.31.99.0/24}"

die() {
    echo "[broker] FAIL: $* (fail closed — refusing to serve)" >&2
    exit 1
}

# --- optional WireGuard upstream (bring-your-own endpoint, fail closed) -----------
# run.sh mounts the user's wg-quick config at /run/wg-source.conf and gives us a
# tmpfs /etc/wireguard: this wg build sandboxes itself (Landlock) and refuses to
# read config files anywhere but /etc/wireguard, so the stripped copy goes there.
if [ -f /run/wg-source.conf ]; then
    ADDR=$(awk -F'= *' '$1 ~ /^Address/ {print $2; exit}' /run/wg-source.conf)
    EP=$(awk -F'= *' '$1 ~ /^Endpoint/ {print $2; exit}' /run/wg-source.conf)
    [ -n "$ADDR" ] || die "wg config has no Address"
    [ -n "$EP" ] || die "wg config has no Endpoint"
    EP_IP=${EP%:*}
    case "$EP_IP" in
        *[!0-9.]*) die "wg Endpoint must be an IPv4 literal (got ${EP_IP}) — there is no DNS before the tunnel" ;;
    esac
    # wg setconf takes only wg(8) keys; Address/DNS/MTU etc. are wg-quick extensions.
    grep -viE '^[[:space:]]*(Address|DNS|MTU|Table|PreUp|PostUp|PreDown|PostDown|SaveConfig)[[:space:]]*=' \
        /run/wg-source.conf > /etc/wireguard/wg0.conf
    ip link add wg0 type wireguard 2>/dev/null \
        || die "cannot create wg0 — need NET_ADMIN (run.sh --wg adds it) and the host wireguard module (sudo modprobe wireguard)"
    wg setconf wg0 /etc/wireguard/wg0.conf || die "wg setconf rejected the config"
    ip addr add "$ADDR" dev wg0
    ip link set up dev wg0
    GW=$(ip route | awk '/^default via/ {print $3; exit}')
    [ -n "$GW" ] || die "no default route to pin the wg endpoint through"
    ip route add "${EP_IP}/32" via "$GW"
    ip route replace default dev wg0
    # A handshake needs traffic; poke DNS through the tunnel until it completes.
    hs=0
    i=0
    while [ "$i" -lt 15 ]; do
        hs=$(wg show wg0 latest-handshakes | awk '{print $2; exit}')
        [ -n "$hs" ] && [ "$hs" != "0" ] && break
        drill example.com @9.9.9.9 >/dev/null 2>&1 || true
        sleep 1
        i=$((i + 1))
    done
    { [ -n "$hs" ] && [ "$hs" != "0" ]; } || die "wireguard handshake timed out — tunnel down, not leaking to the LAN"
    echo "[broker] wireguard up — all egress via wg0, endpoint pinned via ${GW}"
fi

# --- filtered DNS (DoH + blocklist) ------------------------------------------------
mkdir -p /var/cache/dnscrypt-proxy
dnscrypt-proxy -config /etc/dnscrypt-proxy/dnscrypt-proxy.toml &
DNS_PID=$!
ok=0
i=0
while [ "$i" -lt 60 ]; do
    kill -0 "$DNS_PID" 2>/dev/null || die "dnscrypt-proxy exited during startup"
    if drill example.com @127.0.0.1 2>/dev/null | grep -q 'rcode: NOERROR'; then
        ok=1
        break
    fi
    sleep 1
    i=$((i + 1))
done
[ "$ok" = 1 ] || die "filtered DNS did not become ready"
echo "[broker] filtered DoH DNS ready"
if drill doubleclick.net @127.0.0.1 2>/dev/null | grep -q 'rcode: NOERROR'; then
    echo "[broker] WARNING: DNS blocklist did not block a known ad domain" >&2
else
    echo "[broker] DNS blocklist active"
fi

# --- SOCKS5 choke point -------------------------------------------------------------
# External interface = whatever currently carries the default route (wg0 when the
# tunnel is up, the egress bridge otherwise) — decided here, after routing is final.
EG_IF=$(ip route get 9.9.9.9 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p' | sed -n 1p)
[ -n "$EG_IF" ] || die "no egress interface for the SOCKS external side"
cat > /tmp/sockd.conf <<EOF
logoutput: stderr
internal: ${INT_IP} port = 1080
external: ${EG_IF}
socksmethod: none
clientmethod: none
user.privileged: root
user.notprivileged: nobody
client pass {
    from: ${INT_SUBNET} to: 0.0.0.0/0
    log: error
}
socks pass {
    from: ${INT_SUBNET} to: 0.0.0.0/0
    log: error connect disconnect
}
EOF
sockd -f /tmp/sockd.conf &
SOCKD_PID=$!
ok=0
i=0
while [ "$i" -lt 15 ]; do
    kill -0 "$SOCKD_PID" 2>/dev/null || die "sockd exited during startup"
    # 1080 = 0x0438 — check the listener exists without needing netstat flags
    if [ "$(grep -c ':0438' /proc/net/tcp)" -ge 1 ]; then
        ok=1
        break
    fi
    sleep 1
    i=$((i + 1))
done
[ "$ok" = 1 ] || die "sockd never opened ${INT_IP}:1080"

echo "[broker] ready — SOCKS5 choke point on ${INT_IP}:1080, egress via ${EG_IF}"
wait "$SOCKD_PID"
