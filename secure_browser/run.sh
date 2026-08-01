#!/usr/bin/env bash
# Launch the secure travel browser.
#
#   ./run.sh [url]                          direct mode: pasta pinned to the wifi adapter
#   ./run.sh --brokered [--wg conf] [url]   default-deny mode: browser has NO routes at
#                                           all; its only reachable host is the broker
#                                           (SOCKS5 + filtered DoH DNS + optional
#                                           WireGuard upstream, fail closed)
#   flags: --build (force rebuild)  --selftest (headless end-to-end check, used by uat.sh)
#
# Host requirements: linux, bash, rootless podman >= 5 (pasta). Nothing else — the
# policy merge runs in a container, and images auto-load from images/*.tar.gz (made by
# pack.sh) so no network is needed to deploy. Docker is NOT supported: the wifi
# pinning and rootless isolation model are built on podman's pasta.
#
# Containment contract enforced here (see Dockerfile/policies.json for the rest):
#   * Egress ONLY via the wireless adapter: direct mode binds pasta to the
#     auto-detected wifi interface with the container→host gateway mapping removed;
#     brokered mode pins the rootless-netns pasta the same way and VERIFIES it.
#   * No inbound: no ports published, nothing forwarded — unreachable from the LAN.
#   * No path to host disk: read-only rootfs; profile, downloads, /tmp, /run are
#     noexec/nosuid RAM tmpfs destroyed on exit. Only read-only host mounts
#     (display socket, X cookie, merged policy, wg config).
#   * No privilege: cap_drop ALL, no-new-privileges, pid/memory limits. Exactly two
#     capabilities are added back to the browser — SETFCAP + SYS_CHROOT, scoped to
#     the rootless user namespace — so Firefox's OWN content-process sandbox stays
#     enabled as an inner defense layer (glycin's bwrap image loaders need the same).
set -euo pipefail
cd "$(dirname "$0")"

IMG=localhost/secure-browser
BROKER_IMG=localhost/secure-browser-broker
NAME=secure-browser
BROKER_NAME=secure-browser-broker
NET_INT=secure-browser-int
NET_EGRESS=secure-browser-egress
INT_SUBNET=172.31.99.0/24
BROKER_IP=172.31.99.2
PASTA_DROPIN="${XDG_CONFIG_HOME:-$HOME/.config}/containers/containers.conf.d/50-secure-browser-pasta.conf"

# --- dynamic wireless adapter discovery -------------------------------------------
# A wireless interface is one the kernel gives a wireless/ sysfs node. Prefer one
# that is up and addressed; if the only wifi present isn't connected, say so rather
# than silently using some other (wired) path.
wifi_iface() {
    local iface cand=""
    for d in /sys/class/net/*/wireless; do
        [ -e "$d" ] || continue
        iface=$(basename "$(dirname "$d")")
        cand=${cand:-$iface}
        if [ "$(cat "/sys/class/net/${iface}/operstate")" = "up" ] \
           && ip -4 -brief addr show "$iface" | grep -q '[0-9]\.'; then
            echo "$iface"
            return 0
        fi
    done
    if [ -n "$cand" ]; then
        echo "ERROR: wireless adapter ${cand} found but not connected — join the wifi first" >&2
    else
        echo "ERROR: no wireless adapter on this machine" >&2
    fi
    return 1
}

# Offline-first image acquisition: exists -> load from images/ (pack.sh output) ->
# build (needs network; do it at home, not at the hotel).
ensure_image() {
    local img=$1 ctx=$2
    local tarball="images/$(basename "$img").tar.gz"
    if [ "$BUILD" = 1 ] || ! podman image exists "$img"; then
        if [ "$BUILD" = 0 ] && [ -f "$tarball" ]; then
            echo "[run] loading ${img} from ${tarball} (offline)"
            podman load -i "$tarball" >/dev/null
        else
            echo "[run] building ${img}"
            podman build -t "$img" "$ctx"
        fi
    fi
}

BUILD=0 SELFTEST=0 BROKERED=0 WG_CONF=""
while [ $# -gt 0 ]; do
    case "$1" in
        --build)    BUILD=1 ;;
        --selftest) SELFTEST=1 ;;
        --brokered) BROKERED=1 ;;
        --wg)       shift; WG_CONF=$(readlink -f "$1") ;;
        --*)        echo "usage: $0 [--build] [--brokered] [--wg conf] [--selftest] [url]" >&2; exit 2 ;;
        *)          break ;;
    esac
    shift
done
URL="${1:-about:blank}"

IFACE=$(wifi_iface)
WIFI_IP=$(ip -4 -brief addr show "$IFACE" | awk '{print $3}' | cut -d/ -f1)
echo "[run] wireless adapter: ${IFACE} (${WIFI_IP})"

ensure_image "$IMG" .
[ "$BROKERED" = 1 ] && ensure_image "$BROKER_IMG" broker/

# --- hardened browser invocation, shared by both modes -----------------------------
BROWSER_ARGS=(
    --read-only
    --tmpfs /home/browser:rw,noexec,nosuid,nodev,size=1g,mode=0700
    --tmpfs /tmp:rw,noexec,nosuid,nodev,size=256m
    --tmpfs /run:rw,noexec,nosuid,nodev,size=16m
    --shm-size 1g
    --cap-drop ALL --cap-add SETFCAP --cap-add SYS_CHROOT
    --security-opt no-new-privileges
    --pids-limit 2048 --memory 6g
    --hostname localhost
    -e "SB_URL=${URL}"
)

DISPLAY_ARGS=()
if [ "$SELFTEST" = 1 ]; then
    DISPLAY_ARGS+=(-e SB_SELFTEST=1)
    if [ "$BROKERED" = 1 ]; then
        # brokered proof: the browser netns must have no direct egress at all
        DISPLAY_ARGS+=(-e SB_EXPECT_NO_DIRECT=1)
    else
        # direct proof: the egress source address must be the wifi adapter's
        DISPLAY_ARGS+=(-e "SB_EXPECT_IP=${WIFI_IP}")
    fi
elif [ -n "${WAYLAND_DISPLAY:-}" ] && [ -S "${XDG_RUNTIME_DIR:-/nonexistent}/${WAYLAND_DISPLAY}" ]; then
    # Native Wayland: unlike X11, clients can't snoop each other's windows/keystrokes.
    DISPLAY_ARGS+=(
        -v "${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}:/run/wayland/${WAYLAND_DISPLAY}"
        -e XDG_RUNTIME_DIR=/run/wayland
        -e "WAYLAND_DISPLAY=${WAYLAND_DISPLAY}"
    )
    echo "[run] display: wayland"
elif [ -n "${DISPLAY:-}" ]; then
    DISPLAY_ARGS+=(-v /tmp/.X11-unix:/tmp/.X11-unix:ro -e "DISPLAY=${DISPLAY}")
    if [ -n "${XAUTHORITY:-}" ] && [ -f "$XAUTHORITY" ]; then
        DISPLAY_ARGS+=(-v "${XAUTHORITY}:/run/Xauthority:ro" -e XAUTHORITY=/run/Xauthority)
    fi
    echo "[run] display: x11 (${DISPLAY})"
else
    echo "ERROR: no Wayland or X11 display found" >&2
    exit 2
fi

# ======================= direct mode =======================
if [ "$BROKERED" = 0 ]; then
    exec podman run --rm --name "$NAME" \
        --network "pasta:-i,${IFACE},--no-map-gw" \
        "${BROWSER_ARGS[@]}" "${DISPLAY_ARGS[@]}" \
        "$IMG"
fi

# ======================= brokered mode =======================
MERGED_POLICY=""
cleanup() {
    podman rm -f -t 5 "$NAME" >/dev/null 2>&1 || true
    podman rm -f -t 5 "$BROKER_NAME" >/dev/null 2>&1 || true
    podman network rm "$NET_INT" >/dev/null 2>&1 || true
    podman network rm "$NET_EGRESS" >/dev/null 2>&1 || true
    [ -n "$MERGED_POLICY" ] && rm -f "$MERGED_POLICY"
    rm -f "$PASTA_DROPIN"
}
trap cleanup EXIT INT TERM

# Bridge-network egress leaves through the per-user rootless pasta, so the wifi pin
# moves to a containers.conf drop-in (removed on exit). If another rootless netns is
# already up the drop-in won't apply to it — the verification below fails hard
# rather than letting traffic ride an unpinned path.
running=$(podman ps -q | wc -l)
if [ "$running" -gt 0 ]; then
    echo "[run] note: ${running} other container(s) running — if any use bridge networking, the wifi-pin verification below may fail; stop them if it does"
fi
mkdir -p "$(dirname "$PASTA_DROPIN")"
printf '[network]\npasta_options = ["-i", "%s", "--no-map-gw"]\n' "$IFACE" > "$PASTA_DROPIN"

podman network exists "$NET_INT" || podman network create --internal --subnet "$INT_SUBNET" "$NET_INT" >/dev/null
podman network exists "$NET_EGRESS" || podman network create "$NET_EGRESS" >/dev/null

# dante drops to an unprivileged user after binding (SETUID/SETGID), dnscrypt binds
# port 53 (NET_BIND_SERVICE); NET_ADMIN is added only when a WireGuard tunnel has to
# be configured.
BROKER_CAPS=(--cap-drop ALL --cap-add SETUID --cap-add SETGID --cap-add NET_BIND_SERVICE)
WG_ARGS=()
if [ -n "$WG_CONF" ]; then
    [ -f "$WG_CONF" ] || { echo "ERROR: wg config not found: ${WG_CONF}" >&2; exit 2; }
    BROKER_CAPS+=(--cap-add NET_ADMIN)
    # wg self-sandboxes (Landlock) and only reads configs under /etc/wireguard, so
    # the user conf mounts elsewhere and the entrypoint writes the runtime copy
    # into a tmpfs /etc/wireguard.
    WG_ARGS+=(
        -v "${WG_CONF}:/run/wg-source.conf:ro"
        --tmpfs /etc/wireguard:rw,nosuid,nodev,size=1m
    )
fi

podman run -d --name "$BROKER_NAME" \
    --network "${NET_INT}:ip=${BROKER_IP}" --network "$NET_EGRESS" \
    --dns 127.0.0.1 \
    --read-only \
    --tmpfs /tmp:rw,nosuid,nodev,size=64m \
    --tmpfs /var/cache:rw,nosuid,nodev,size=64m \
    --tmpfs /run:rw,nosuid,nodev,size=16m \
    "${BROKER_CAPS[@]}" \
    --security-opt no-new-privileges \
    --pids-limit 512 --memory 512m \
    -e "SB_INT_IP=${BROKER_IP}" -e "SB_INT_SUBNET=${INT_SUBNET}" \
    "${WG_ARGS[@]}" \
    "$BROKER_IMG" >/dev/null

echo "[run] waiting for broker (tunnel -> filtered DNS -> SOCKS5)..."
ready=0
for _ in $(seq 1 90); do
    state=$(podman inspect -f '{{.State.Status}}' "$BROKER_NAME" 2>/dev/null || echo gone)
    [ "$state" = "running" ] || break
    if [ "$(podman logs "$BROKER_NAME" 2>&1 | grep -c '\[broker\] ready')" -ge 1 ]; then
        ready=1
        break
    fi
    sleep 1
done
if [ "$ready" != 1 ]; then
    echo "---- broker logs ----" >&2
    podman logs "$BROKER_NAME" 2>&1 | tail -30 >&2 || true
    echo "ERROR: broker failed to become ready" >&2
    exit 1
fi
podman logs "$BROKER_NAME" 2>&1 | grep '\[broker\]' || true

# Verify the wifi pin actually took. Two acceptable proofs:
#   1. the rootless-netns pasta carries "-i <wifi>" (our drop-in applied), or
#   2. a rootless netns pre-existed (other containers running) but the HOST's own
#      default egress is the wifi adapter — pasta without -i follows the default
#      route, so the effective path is still the wifi.
# Neither holding means traffic could ride a non-wifi path: fail hard.
pin=""
for c in /proc/[0-9]*/cmdline; do
    line=$(tr '\0' ' ' < "$c" 2>/dev/null) || continue
    case "$line" in
        *pasta*"-i ${IFACE} "*) pin="rootless pasta running with '-i ${IFACE}'"; break ;;
    esac
done
if [ -z "$pin" ]; then
    hostdev=$(ip route get 9.9.9.9 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p' | sed -n 1p)
    if [ "$hostdev" = "$IFACE" ]; then
        pin="pre-existing rootless netns; host default egress dev is ${hostdev} (the wifi adapter)"
    fi
fi
if [ -z "$pin" ]; then
    echo "ERROR: cannot prove egress rides ${IFACE} — a rootless netns existed before the drop-in was written AND the host default route is not the wifi; stop other rootless containers and retry" >&2
    exit 1
fi
echo "[run] pasta egress pinned to ${IFACE} verified: ${pin}"

# Runtime policy: base STIG policy + locked SOCKS5-to-broker + DoH off (the broker
# does filtered DoH; browser-side DoH would bypass the blocklist). Merged in a
# container so the host needs nothing but podman; mounted read-only over both
# policy paths Firefox reads.
MERGED_POLICY=$(mktemp)
podman run --rm --network none -v "$(pwd)/policies.json:/base.json:ro" \
    --entrypoint python3 "$IMG" -c "
import json
d = json.load(open('/base.json'))
p = d['policies']
p['Proxy'] = {'Mode': 'manual', 'Locked': True,
              'SOCKSProxy': '${BROKER_IP}:1080', 'SOCKSVersion': 5,
              'UseProxyForDNS': True}
p['DNSOverHTTPS'] = {'Enabled': False, 'Locked': True}
print(json.dumps(d))
" > "$MERGED_POLICY"
[ -s "$MERGED_POLICY" ] || { echo "ERROR: policy merge failed" >&2; exit 1; }

echo "[run] launching browser (default-deny: its only route is the broker's SOCKS5)"
set +e
podman run --rm --name "$NAME" \
    --network "$NET_INT" \
    -v "${MERGED_POLICY}:/usr/lib/firefox-esr/distribution/policies.json:ro" \
    -v "${MERGED_POLICY}:/etc/firefox/policies/policies.json:ro" \
    "${BROWSER_ARGS[@]}" "${DISPLAY_ARGS[@]}" \
    "$IMG"
rc=$?
set -e

# In selftest, surface the choke point's own traffic log — independent evidence that
# the page fetch really traversed the broker rather than some other path.
if [ "$SELFTEST" = 1 ]; then
    echo "---- broker choke-point log (sockd) ----"
    podman logs "$BROKER_NAME" 2>&1 | grep 'tcp/connect' | tail -5 || true
fi
exit "$rc"
