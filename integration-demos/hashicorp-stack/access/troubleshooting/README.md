# Troubleshooting — where the comm path breaks down

The access path has **five hops**. A failure at any one looks like "I can't
reach Boundary", so diagnose in order — each hop's check assumes the ones before
it pass.

```
 (1) workstation node ──register──► headscale        control-plane registration
 (2) workstation node ◄──tunnel──►  bastion node     WireGuard / DERP data path
 (3) workstation ──:9200 allowed?─► bastion          headscale ACL policy
 (4) bastion broker ──forward────►  Boundary         socat target forwarding
 (5) bastion ──resolve name──────►  CoreDNS          secure DNS (if using names)
```

Container names below are the UAT/compose names (`acc-*` in the UAT; `endpoint-ts`,
`bastion-ts`, `bastion-headscale`, `bastion-broker` in the deploy composes).
Substitute your own.

## Fast triage

| Symptom | Most likely hop | Jump to |
|---|---|---|
| workstation node has no `100.64.x` address | 1 | [Hop 1](#hop-1--registration) |
| both nodes have IPs but `tailscale ping` times out | 2 | [Hop 2](#hop-2--tunnel) |
| ping works but the brokered port hangs/refuses | 3 or 4 | [Hop 3](#hop-3--policy), [Hop 4](#hop-4--broker) |
| an internal host you *expected* to reach is unreachable | 3/4 (by design) | [Hop 3](#hop-3--policy) |
| an internal host you should *not* reach IS reachable | leak | [Leaks](#leaks--false-reachability) |
| target resolves to the wrong IP / NXDOMAIN | 5 | [Hop 5](#hop-5--dns) |

---

## Hop 1 — registration

**Check:** `podman exec endpoint-ts tailscale ip -4` → expect `100.64.x`.
`podman exec bastion-headscale headscale nodes list` → both nodes present.

**`NeedsLogin` / no IP, node never appears:**

- **`TS_LOGIN_SERVER` was ignored.** The tailscale image does **not** read it.
  The login server must be in `TS_EXTRA_ARGS`:
  `TS_EXTRA_ARGS=--login-server=http://<headscale>:8080`.
- **Container-name DNS is unreliable once `tailscaled` starts** (it manages
  `/etc/resolv.conf`). Point `--login-server` and headscale's `server_url` at a
  **static IP**, not a container name. Symptom in logs:
  `failed to resolve "headscale": no DNS fallback candidates`.
  `podman logs endpoint-ts | grep -i 'resolve\|bootstrap'`.
- **`changing settings via 'tailscale up' requires --reset`.** State from a
  previous run. The container image handles first boot; if you re-`up` by hand,
  add `--reset`. In the compose flow, `down -v` clears it.
- **Bad/expired/one-time pre-auth key.** Mint a fresh reusable key:
  `headscale preauthkeys create --user <id> --reusable --expiration 1h`.
- **headscale won't start** → `podman logs bastion-headscale`. v0.29 refuses to
  boot unless DNS is coherent:
  `dns.nameservers.global must be set when dns.override_local_dns is true` →
  set `dns.override_local_dns: false` (see `config/headscale.yaml`).
- **Wrong image tag.** headscale `v0.29.2`, tailscale **`v1.98.9`** (the tag has
  a leading `v`; `1.98.9` returns `manifest unknown`).

## Hop 2 — tunnel

**Check:** `podman exec endpoint-ts tailscale ping --timeout 8s bastion` →
expect `pong from bastion ... via <ip>`.

**`ping ... timed out` though both nodes are registered:**

- **No common DERP relay.** When the two nodes are on networks that can't reach
  each other directly, they relay through headscale's embedded DERP — which both
  must be able to reach. If the bastion is on an isolated internal segment, it
  **must also be on the public side** (dual-homed) so it can reach the same DERP
  the workstation uses. Symptom: `tailscale status` shows the peer but
  `relay="-"` and a DERP health warning.
- **DERP disabled/misconfigured.** `derp.server.enabled: true` and
  `stun_listen_addr: 0.0.0.0:3478` must be set, and `:3478/udp` reachable.
- A direct path is fine too: if both nodes share a segment, `tailscale ping`
  reports `via <that-ip>` and no DERP is needed.

## Hop 3 — policy

**Check:** the authorized port works, a non-allowed port is refused:
```
podman exec acc-workstation sh -c 'curl -s --max-time 6 --socks5-hostname 127.0.0.1:1055 http://<bastion-100.64-ip>:9200/'   # allowed  -> reply
podman exec acc-workstation sh -c 'curl -s --max-time 6 --socks5-hostname 127.0.0.1:1055 http://<bastion-100.64-ip>:2222/'   # denied   -> empty
```

**Everything is denied (even the port you meant to allow):**

- **Policy not loaded / syntax error.** `podman logs bastion-headscale | grep -i policy`.
  huJSON must be valid; reload with `headscale` restart or `SIGHUP` after edits.
  Confirm `policy.mode: file` and `policy.path` in the config.
- **`src`/`dst` mismatch.** Rules are `endpoint@ → bastion@:<port>`. The `src`
  user must match the workstation's key owner and `dst` the bastion's. List
  owners: `headscale nodes list` (User column).
- **Deny by default is working as intended.** A port that isn't in an `accept`
  rule is *supposed* to be blocked — see [Hop 4](#hop-4--broker) if you meant to
  allow it.

**A `curl` to a tailnet address hangs instead of failing fast:** you're dialing
a `100.64.x`/tunnel destination without the SOCKS proxy. Tailnet destinations
live in `tailscaled`'s userspace netstack — you must dial them through
`--socks5-hostname 127.0.0.1:1055`, not directly.

## Hop 4 — broker

**Check:** the broker is listening and can reach the target:
```
podman exec bastion-ts sh -c 'netstat -ltn | grep -E ":9200|:9202"'   # broker listeners
podman exec bastion-broker sh -c 'apk add -q curl; curl -s http://boundary:9200/'   # broker -> target
podman logs bastion-broker    # "broker: :9200 -> boundary:9200"
```

**Port reachable over the tunnel but the reply hangs/refuses:**

- **No forwarder for that port.** The broker only forwards `BROKER_TARGETS`
  entries. Add `9202=boundary:9202` (and the matching ACL rule). This is the
  allow-list; keep `BROKER_TARGETS` and `policy.hujson` in lock-step.
- **Broker can't reach the target.** The broker shares the bastion node's netns;
  the bastion must be on the internal segment and able to reach the target host.
  Test from the broker (above). Fix DNS/routing on the bastion, or use an IP in
  `BROKER_TARGETS`.
- **Broker container exited.** `podman ps -a | grep broker`. On the internal
  segment `apk add socat` fails (no internet) — the broker image must already
  have socat, or the bastion must be dual-homed so `apk` works.

## Hop 5 — DNS

**Check:** `podman exec bastion-broker sh -c 'apk add -q bind-tools; dig +short @<coredns-ip> boundary.hashi.internal'` → expect the target IP.

- **`connection refused`:** you queried the wrong host. CoreDNS is a **separate
  container with its own IP** — don't query headscale's IP. Give CoreDNS a
  static address and query that.
- **`SERVFAIL` on external names:** the DoT upstream is unreachable. CoreDNS
  needs outbound `853/tcp` to Quad9; `podman logs <coredns>`.
- **Wrong internal IP:** fix the `hosts` block in `config/Corefile`.

---

## Leaks — false reachability

If a workstation reaches an internal host it should **not** (the dangerous
failure), it is almost always a **host-bridge leak**, not a tailnet grant:

- Sibling Podman bridge networks route to each other when the host has
  `net.ipv4.ip_forward=1`. A workstation container on the "wan" bridge can then
  reach the "lan" bridge **directly**, bypassing the tunnel entirely.
- **Fix:** make the internal network `internal: true` (compose) — Podman then
  drops forwarded traffic in/out of it, so the tunnel is the only path. Verify:
  ```
  podman exec acc-workstation sh -c 'curl -s --max-time 4 http://<internal-ip>:<port>/'   # must be EMPTY
  ```
  In a real deployment the workstation is on the actual internet and physically
  cannot reach the internal segment — the `internal: true` network reproduces
  that for the UAT.

## UAT-specific gotchas

- **`podman run --network container:X` fails with "part of a pod".**
  podman-compose puts services in a pod; a standalone `podman run` can't join a
  pod member's netns. Add a helper **service** with `network_mode: "service:X"`
  and `podman exec` into it (the UAT's `workstation` service).
- **`ports:` on a `network_mode: service:` service is rejected.** Published
  ports go on the **netns owner** (`endpoint-ts`), not the netns-sharer
  (`forward`).
- **`socat` SOCKS5 syntax:**
  `SOCKS5-CONNECT:<socks-server>:<socks-port>:<target-host>:<target-port>`.
- **A negative check that "passes" because the command errored is a false pass.**
  Always confirm the *positive* path works with the same harness first, so an
  empty result genuinely means "blocked", not "the test tool broke".
