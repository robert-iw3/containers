#!/bin/sh
# Container entrypoint: launch the hardened travel browser.
#
# Everything writable lives on tmpfs mounted by run.sh (/home/browser, /tmp, shm) —
# the profile and any downloads exist only for the life of the container. The STIG
# policy's SanitizeOnShutdown clears browser state as well.
#
# Firefox's own content-process sandbox stays ENABLED — defense-in-depth on top of
# the container boundary. It needs to map uid 0 into a nested user namespace
# (CAP_SETFCAP on kernels >= 5.12) and chroot its content processes (CAP_SYS_CHROOT);
# run.sh grants exactly those two capabilities, scoped to the rootless user namespace.
# The same grant lets glycin's bwrap-sandboxed image loaders (gdk-pixbuf on Alpine)
# run instead of aborting GTK. The selftest below proves all of this with evidence.
set -eu

PROFILE="${HOME}/profile"
mkdir -p "$PROFILE" "${HOME}/Downloads"

echo "[browser] STIG policy: $(test -f /usr/lib/firefox-esr/distribution/policies.json && echo present || echo MISSING)"

# --- self-test mode (used by uat.sh via run.sh --selftest; headless, no display) ---
# Every security claim is proven by an observable probe and the evidence is printed.
if [ "${SB_SELFTEST:-0}" = "1" ]; then
    fail() { echo "[selftest] FAIL: $*" >&2; exit 1; }

    # CLAIM: capabilities are exactly SETFCAP(31)+SYS_CHROOT(18) = 0x80040000.
    caps=$(awk '/^CapEff/{print $2}' /proc/self/status)
    [ "$caps" = "0000000080040000" ] \
        || fail "capability set is CapEff=${caps}, expected 0000000080040000 (SETFCAP+SYS_CHROOT only)"
    echo "[selftest] EVIDENCE caps: CapEff=${caps} == SETFCAP+SYS_CHROOT only"

    # CLAIM: root filesystem is immutable.
    root_opts=$(awk '$2 == "/" {print $4; exit}' /proc/mounts)
    if touch /usr/.rw-probe 2>/dev/null; then
        fail "root filesystem is writable"
    fi
    echo "[selftest] EVIDENCE rootfs: write to /usr denied; / mounted with (${root_opts})"

    # CLAIM: anything a page drops into browser-writable space cannot execute.
    home_opts=$(awk '$2 == "/home/browser" {print $4; exit}' /proc/mounts)
    case "$home_opts" in *noexec*) : ;; *) fail "/home/browser lacks noexec (${home_opts})" ;; esac
    printf '#!/bin/sh\ntrue\n' > /home/browser/.exec-probe && chmod +x /home/browser/.exec-probe
    if exec_err=$(/home/browser/.exec-probe 2>&1); then
        fail "dropped file executed from browser tmpfs"
    fi
    echo "[selftest] EVIDENCE noexec: /home/browser (${home_opts}); exec attempt -> ${exec_err}"

    # CLAIM (direct mode): egress source address is the wifi adapter's address.
    if [ -n "${SB_EXPECT_IP:-}" ]; then
        got=$(python3 -c 'import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("9.9.9.9", 53)); print(s.getsockname()[0])')
        [ "$got" = "$SB_EXPECT_IP" ] \
            || fail "egress source ${got}, expected wifi address ${SB_EXPECT_IP}"
        echo "[selftest] EVIDENCE egress: source ${got} == wifi adapter address — pinned OK"
    fi

    # CLAIM (brokered mode): this netns has NO direct route off the machine.
    if [ "${SB_EXPECT_NO_DIRECT:-0}" = "1" ]; then
        direct=$(python3 -c '
import socket
try:
    socket.create_connection(("9.9.9.9", 443), timeout=5)
    print("CONNECTED")
except Exception as e:
    print(f"{type(e).__name__}: {e}")')
        case "$direct" in
            CONNECTED*) fail "direct egress possible from browser netns" ;;
        esac
        echo "[selftest] EVIDENCE no-direct-egress: connect 9.9.9.9:443 -> ${direct}"
    fi

    # CLAIM: firefox runs with its inner sandbox intact and renders a real page
    # over the only permitted path (pinned pasta, or the broker SOCKS5).
    firefox-esr --profile "$PROFILE" --no-remote --headless \
        --screenshot /home/browser/selftest.png "${SB_URL:-about:blank}" \
        > /home/browser/firefox.log 2>&1 || { cat /home/browser/firefox.log; fail "firefox exited non-zero"; }
    sandbox_errs=$(grep -cE 'Sandbox:.*(EPERM|EACCES)|exited on signal' /home/browser/firefox.log) || true
    if [ "$sandbox_errs" -ne 0 ]; then
        cat /home/browser/firefox.log
        fail "firefox inner sandbox is broken (${sandbox_errs} sandbox errors)"
    fi
    echo "[selftest] EVIDENCE inner sandbox: ${sandbox_errs} sandbox errors in firefox log — healthy"
    [ -s /home/browser/selftest.png ] || fail "firefox produced no screenshot"
    echo "[selftest] EVIDENCE fetch: rendered ${SB_URL:-about:blank} ($(wc -c < /home/browser/selftest.png) bytes) via contained firefox"
    echo "[selftest] all probes passed"
    exit 0
fi

# --- interactive mode --------------------------------------------------------------
# Prefer native Wayland (no cross-client snooping, unlike X11); fall back to X11.
if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -S "${XDG_RUNTIME_DIR:-/run/wayland}/${WAYLAND_DISPLAY}" ]; then
    export MOZ_ENABLE_WAYLAND=1
    echo "[browser] display: wayland (${WAYLAND_DISPLAY})"
elif [ -n "${DISPLAY:-}" ]; then
    echo "[browser] display: x11 (${DISPLAY})"
else
    echo "[browser] no display — run.sh should have mounted the Wayland or X11 socket" >&2
    exit 2
fi

exec firefox-esr --profile "$PROFILE" --no-remote "${SB_URL:-about:blank}"
