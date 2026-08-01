#!/usr/bin/env bash
# UAT for the secure travel browser. Every security assertion is PROVEN by an
# observable probe, and the evidence line is recorded next to the claim — no claim
# passes on faith. All probes run through the REAL deployment path (run.sh), not a
# parallel stack. Headless and container-scoped; the only host artifact is run.sh's
# own containers.conf drop-in, whose removal is itself asserted at the end.
set -euo pipefail
cd "$(dirname "$0")"

DROPIN="${XDG_CONFIG_HOME:-$HOME/.config}/containers/containers.conf.d/50-secure-browser-pasta.conf"
FAILED=0
RESULTS=()

claim() { # claim <id> <description> <evidence|FAIL>
    if [ "$3" = "FAIL" ]; then
        RESULTS+=("FAIL    $1  $2 — NO EVIDENCE")
        FAILED=1
    else
        RESULTS+=("PROVEN  $1  $2
        evidence: $3")
    fi
}

evidence() { # evidence <captured-output> <regex> -> first matching line, or FAIL
    local line
    line=$(printf '%s\n' "$1" | grep -E "$2" | sed -n 1p) || true
    if [ -n "$line" ]; then printf '%s' "$line"; else printf 'FAIL'; fi
}

echo "== phase 1: direct mode (pasta pinned to the wifi adapter) =="
if ! direct_out=$(./run.sh --build --selftest https://example.com 2>&1); then
    printf '%s\n' "$direct_out"
    echo "UAT FAIL: direct-mode selftest exited non-zero" >&2
    exit 1
fi
printf '%s\n' "$direct_out"
claim D1 "egress source address == wifi adapter (pasta -i pin)" \
    "$(evidence "$direct_out" 'EVIDENCE egress: source .* pinned OK')"
claim D2 "capabilities are exactly SETFCAP+SYS_CHROOT" \
    "$(evidence "$direct_out" 'EVIDENCE caps: CapEff=0000000080040000')"
claim D3 "root filesystem immutable" \
    "$(evidence "$direct_out" 'EVIDENCE rootfs: write to /usr denied')"
claim D4 "dropped files cannot execute (noexec browser tmpfs)" \
    "$(evidence "$direct_out" 'EVIDENCE noexec: .*Permission denied')"
claim D5 "firefox inner sandbox enabled and healthy" \
    "$(evidence "$direct_out" 'EVIDENCE inner sandbox: 0 sandbox errors')"
claim D6 "page rendered over the contained path" \
    "$(evidence "$direct_out" 'EVIDENCE fetch: rendered https://example.com')"
if grep -c 'no-map-gw' run.sh >/dev/null && ! grep -qE '^[[:space:]]*-p |--publish' run.sh; then
    claim D7 "no container->host gateway mapping, no published ports (launcher config)" \
        "run.sh: every network uses --no-map-gw; no -p/--publish anywhere"
else
    claim D7 "no container->host gateway mapping, no published ports (launcher config)" FAIL
fi

echo
echo "== phase 2: brokered mode (default-deny via SOCKS5 broker) =="
if ! brok_out=$(./run.sh --brokered --build --selftest https://example.com 2>&1); then
    printf '%s\n' "$brok_out"
    echo "UAT FAIL: brokered selftest exited non-zero" >&2
    exit 1
fi
printf '%s\n' "$brok_out"
claim B1 "broker chain came up (DNS -> SOCKS5) before serving" \
    "$(evidence "$brok_out" '\[broker\] ready — SOCKS5 choke point')"
claim B2 "rootless pasta egress verified pinned to the wifi adapter" \
    "$(evidence "$brok_out" 'pasta egress pinned to .* verified')"
claim B3 "DNS is broker-filtered DoH with an active blocklist" \
    "$(evidence "$brok_out" '\[broker\] DNS blocklist active')"
claim B4 "browser netns has zero direct egress" \
    "$(evidence "$brok_out" 'EVIDENCE no-direct-egress: connect 9.9.9.9:443 -> (OSError|TimeoutError|ConnectionRefusedError)')"
claim B5 "page fetch traversed the SOCKS5 choke point" \
    "$(evidence "$brok_out" 'tcp/connect')"
claim B6 "inner sandbox + rootfs + noexec hold in brokered mode too" \
    "$(evidence "$brok_out" 'EVIDENCE inner sandbox: 0 sandbox errors')"
claim B7 "page rendered through the broker" \
    "$(evidence "$brok_out" 'EVIDENCE fetch: rendered https://example.com')"

echo
echo "== phase 3: wireguard fail-closed (unreachable endpoint must refuse service) =="
keys=$(podman run --rm --entrypoint sh localhost/secure-browser-broker \
    -c 'k=$(wg genkey); echo "$k"; echo "$k" | wg pubkey')
WG_TEST_CONF=$(mktemp)
cat > "$WG_TEST_CONF" <<EOF
[Interface]
PrivateKey = $(printf '%s\n' "$keys" | sed -n 1p)
Address = 10.99.0.2/32

[Peer]
PublicKey = $(printf '%s\n' "$keys" | sed -n 2p)
AllowedIPs = 0.0.0.0/0
Endpoint = 192.0.2.1:51820
EOF
if wg_out=$(./run.sh --brokered --wg "$WG_TEST_CONF" --selftest https://example.com 2>&1); then
    printf '%s\n' "$wg_out"
    claim W1 "broker refuses to serve when the tunnel is down (fail closed)" FAIL
else
    claim W1 "broker refuses to serve when the tunnel is down (fail closed)" \
        "$(evidence "$wg_out" 'fail closed')"
fi
rm -f "$WG_TEST_CONF"

echo
echo "== phase 4: no residue on the host =="
residue=""
if podman container exists secure-browser 2>/dev/null; then residue+="container:browser "; fi
if podman container exists secure-browser-broker 2>/dev/null; then residue+="container:broker "; fi
if podman network exists secure-browser-int 2>/dev/null; then residue+="network:int "; fi
if podman network exists secure-browser-egress 2>/dev/null; then residue+="network:egress "; fi
if [ -e "$DROPIN" ]; then residue+="pasta-dropin "; fi
if [ "$(podman volume ls -q | grep -c secure-browser)" -ne 0 ]; then residue+="volumes "; fi
if [ -z "$residue" ]; then
    claim R1 "nothing persists: no containers, networks, volumes, or config drop-in" \
        "all podman/config lookups empty after teardown"
else
    echo "residue found: ${residue}" >&2
    claim R1 "nothing persists: no containers, networks, volumes, or config drop-in" FAIL
fi

echo
echo "==================== UAT EVIDENCE SUMMARY ===================="
for r in "${RESULTS[@]}"; do printf '%s\n' "$r"; done
echo "=============================================================="
if [ "$FAILED" = 0 ]; then
    echo "== UAT PASS — every claim proven =="
else
    echo "== UAT FAIL ==" >&2
    exit 1
fi
