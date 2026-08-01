# secure_browser

A disposable, hardened Firefox in a rootless podman container, for browsing from
networks you don't trust (hotel / airport / café wifi). The window appears on your
desktop; everything else stays inside containers and is destroyed when you close it.

## What it's for

- General web browsing, email, banking-grade sites from a hostile LAN.
- Opening links or sites you're not sure about, with nothing to infect: if a page
  drops a payload, it lands on a no-execute RAM disk inside a read-only,
  capability-stripped container and evaporates on exit — it can never reach the host
  filesystem.
- Keeping this laptop quiet on the network: traffic is pinned to the wifi adapter
  only, nothing accepts inbound connections, WebRTC (which leaks your real addresses
  to web pages) is disabled, and DNS never goes to the hotel's resolver.

Not for: browser extensions, DRM video (Netflix etc.), saved logins/bookmarks, or
downloads you want to keep — by design, nothing persists.

## Requirements

Linux with **rootless podman >= 5** (pasta). That's it — every other component runs
in a container. Docker is not supported: the wifi pinning and rootless isolation
model are built on podman's pasta.

## Deploy

**Build and pack on a trusted network, BEFORE you travel.** Building pulls base
images, packages, and the DNS blocklist over the network — never do that on public
wifi. The packed tarballs in `images/` are git-ignored (too big for the repo), so a
fresh clone has no images yet: prepare them while still on a trusted connection:

```bash
cd secure_browser
./uat.sh          # builds the images and PROVES every security claim with evidence
./pack.sh         # exports images to images/*.tar.gz for offline deploy
```

Then copy the whole `secure_browser/` directory (now including `images/`) to the
travel machine. On untrusted wifi nothing is built or pulled — `run.sh` auto-loads
from `images/`:

```bash
./run.sh                           # direct mode
./run.sh --brokered                # default-deny broker mode (recommended)
./run.sh --brokered --wg my.conf   # + WireGuard: hotel sees ONE encrypted tunnel
./travel_mode.sh on                # optional host-side: random MAC, no hostname leak
```

`./run.sh https://some.site` opens a URL; `--build` forces a rebuild — do that (and
re-run `./pack.sh`) on a trusted network only, to pick up Firefox and blocklist
updates. Close the window and containers, profile, cache, cookies, downloads,
networks, and config are all gone — `uat.sh` phase 4 proves it.

## Two modes

**Direct** — Firefox's egress rides pasta bound to the auto-detected wifi adapter
(`--no-map-gw`: the container can't even reach the host). DoH to Quad9 is locked in
the browser policy.

**Brokered (`--brokered`)** — default-deny. The browser sits on an *internal*
network with no routes at all; its only reachable host is a broker container that
carries everything:

```
firefox --locked SOCKS5--> broker [dante + dnscrypt DoH/blocklist (+ wireguard)]
        --> rootless pasta pinned to wifi --> hotel LAN
```

- Every flow is logged at the SOCKS choke point (compromise canary).
- DNS is DoH to Quad9/Cloudflare-security with a ~100k-domain StevenBlack blocklist
  baked into the image — ad/malware domains die at the broker, compensating for the
  no-add-ons policy (no uBlock).
- `--wg <wg-quick-conf>`: routes ALL broker egress through your WireGuard endpoint
  (endpoint must be an IP literal; host may need `sudo modprobe wireguard` once).
  **Fail closed**: if the handshake doesn't complete, the broker refuses to serve —
  proven by UAT phase 3.
- If the broker dies, the browser has nothing — kill-switch by topology.

## How it's contained

| Layer | Control |
|---|---|
| Network egress | pasta bound to the auto-detected wireless interface only (verified, fails hard if the pin didn't take); container→host mapping disabled |
| Network inbound | nothing published, nothing forwarded — unreachable from the LAN |
| Disk | read-only rootfs; profile/downloads/tmp on noexec,nosuid RAM tmpfs; no writable host mounts; RAM-only browser cache |
| Privilege | rootless podman, cap_drop ALL (only SETFCAP+SYS_CHROOT added back so Firefox's own inner sandbox stays enabled), no-new-privileges, pid/memory limits |
| Browser | DISA Firefox STIG-aligned policy: no add-ons, no telemetry, no password manager/autofill, no dev tools, TLS 1.2 floor, sanitize on shutdown — plus HTTPS-Only, WebRTC off |
| DNS | never the hotel resolver: DoH in-browser (direct) or filtered DoH at the broker (brokered) |
| Display | native Wayland when available (X11 fallback), the only host resource shared |

`uat.sh` proves each of these with a printed evidence line (exact capability mask,
denied write, `Permission denied` on the exec probe, failed direct connect from the
browser netns, the sockd log line for the fetch, wg fail-closed refusal, and empty
residue checks).

## Known trade-offs

- No sound (no audio socket is mounted) and no DRM media — deliberate.
- Captive portals: clear the portal in **direct** mode first (HTTPS-Only shows a
  one-click "Continue to HTTP Site"), then relaunch `--brokered`; a wg tunnel can't
  come up behind an uncleared portal.
- Brokered mode writes a containers.conf drop-in pinning rootless pasta to the wifi
  adapter while running (removed on exit); other rootless bridge containers started
  in that window would share the pin, and if one was already running the pin check
  fails hard rather than guessing.
- Clipboard works both ways on purpose (you'll want to paste URLs/passwords).
- tmpfs is RAM and can reach host swap under memory pressure; if that matters,
  use encrypted swap or zram.
