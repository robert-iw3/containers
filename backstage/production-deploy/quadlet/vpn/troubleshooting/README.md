# Troubleshooting — where the comm path breaks down (vpn role)

The remote-access path has **five hops**. A failure at any one looks like "I
can't open the portal", so diagnose in order — each hop's check assumes the ones
before it pass. This is the Quadlet/systemd deployment, so the units are
`portal-headscale`, `portal-bastion-ts`, `portal-vpn-broker`, `portal-vpn-coredns`
and the workstation runs the shared endpoint compose.

```
 (1) workstation node ──register──► portal-headscale     control-plane registration
 (2) workstation node ◄──tunnel──►  portal-bastion-ts    WireGuard / DERP data path
 (3) workstation ──:27007 allowed?► bastion              headscale ACL policy
 (4) portal-vpn-broker ──forward──► Backstage portal     socat target forwarding
 (5) bastion ──resolve name───────► portal-vpn-coredns   secure DNS (if using names)
```

Quadlet turns each `*.container` into a `*.service`; use `systemctl` and
`journalctl -u <unit>` to inspect, and `podman logs/exec <ContainerName>` for the
container itself.

## Fast triage

| Symptom | Most likely hop | Jump to |
|---|---|---|
| workstation has no `100.64.x` address | 1 | [Hop 1](#hop-1--registration) |
| both nodes have IPs but `tailscale ping` times out | 2 | [Hop 2](#hop-2--tunnel) |
| ping works but `localhost:27007` hangs/refuses | 3 or 4 | [Hop 3](#hop-3--policy), [Hop 4](#hop-4--broker) |
| a unit won't start / keeps restarting | any | [Quadlet units](#quadlet--systemd) |
| an internal host you should *not* reach IS reachable | leak | [Leaks](#leaks--false-reachability) |
| target resolves to the wrong IP / NXDOMAIN | 5 | [Hop 5](#hop-5--dns) |

---

## Hop 1 — registration

**Check:**
```
podman exec portal-headscale headscale nodes list        # both nodes present?
podman exec endpoint-ts tailscale ip -4                   # on the workstation
```

**`NeedsLogin` / no IP / node never appears:**

- **`TS_LOGIN_SERVER` is ignored** by the tailscale image — the login server
  must be in `TS_EXTRA_ARGS=--login-server=…` (it is, in `bastion-ts.container`
  and the workstation compose).
- **Container-name DNS is unreliable once `tailscaled` starts.** On the bastion,
  `bastion-ts.container` uses `--login-server=http://portal-headscale:8080`; if
  registration fails with `failed to resolve "portal-headscale"`, pin
  headscale's address instead: give it a fixed IP on `portal.network` (or a
  `/etc/hosts` entry) and use that IP in both the unit and `server_url`.
  `journalctl -u portal-bastion-ts | grep -i 'resolve\|bootstrap'`.
- **`server_url` unreachable from the workstation.** It must be the bastion's
  **public** URL (`VPN_PUBLIC_URL`), not an internal name.
  `curl -sv $VPN_PUBLIC_URL/health` from the internet side.
- **Bad/expired key.** `VPN_BASTION_AUTHKEY` for the bastion (user 1); a fresh
  per-dev key for each workstation (user 2). Reusable, unexpired.
- **headscale unit down** → `systemctl status portal-headscale`,
  `journalctl -u portal-headscale`. v0.29 refuses to boot on incoherent DNS:
  set `dns.override_local_dns: false` (already in the template).

## Hop 2 — tunnel

**Check:** `podman exec endpoint-ts tailscale ping --timeout 8s bastion` →
`pong from bastion …`.

**Times out though both are registered:**

- **The bastion must be dual-homed.** The workstation (internet) and the bastion
  relay through headscale's embedded DERP; both must reach the same DERP. The
  bastion VM needs a public interface (for DERP/workstations) **and**
  `portal.network` (to reach the portal). Publish `:3478/udp` (the unit does).
- **`:8080` / `:3478` blocked by the firewall.** Open them on the bastion's
  public interface only — see the main deploy's firewall matrix.
- `tailscale status` on either node shows the peer and whether the path is
  `direct` or via `derp`.

## Hop 3 — policy

**Check (from the workstation):**
```
curl -s --max-time 6 http://127.0.0.1:27007/     # allowed -> Backstage responds
```
The forwarder maps `127.0.0.1:27007` → SOCKS5 → `bastion:27007`.

**Everything denied, including the port you allowed:**

- **Policy not loaded / bad huJSON.**
  `journalctl -u portal-headscale | grep -i policy`. Fix `config/policy.hujson`,
  then reload: `podman exec portal-headscale kill -HUP 1` (or restart the unit).
- **`src`/`dst` owners mismatch.** Rules are `endpoint@ → bastion@:<port>`; the
  workstation key must belong to user `endpoint`, the bastion node to `bastion`.
- **Port not in the allow-list.** `policy.hujson` **and** `BROKER_TARGETS`
  (`vpn.env`) must both list the port. Default: `27007` (portal) and `9202`
  (Boundary). Deny-by-default means anything else is intentionally blocked.

## Hop 4 — broker

**Check:**
```
podman exec portal-bastion-ts sh -c 'netstat -ltn | grep -E ":27007|:9202"'   # listeners
podman logs portal-vpn-broker                                                 # "broker: :27007 -> …"
podman exec portal-vpn-broker sh -c 'apk add -q curl; curl -s http://<portal-host>:27007/'  # broker -> target
```

- **No forwarder for the port** → add it to `BROKER_TARGETS` in `hosts.env`
  (`vpn.env.template`) and to `policy.hujson`, redeploy the role.
- **Broker can't reach the portal/Boundary.** The broker shares
  `portal-bastion-ts`'s netns; that node is on `portal.network` and must reach
  `${PORTAL_HOST}:27007` / `${ACCESS_HOST}:9202`. Verify name resolution on the
  bastion (Hop 5) or put IPs in `BROKER_TARGETS`.
- **Broker unit restart-looping** → `systemctl status portal-vpn-broker`. The
  broker `apk add socat` needs egress; if the bastion's outbound is locked down,
  pre-bake socat into a broker image instead.

## Hop 5 — DNS

**Check:** `podman exec portal-vpn-broker sh -c 'apk add -q bind-tools; dig +short @<coredns-ip> <portal-host>'`.

- **`connection refused`:** CoreDNS is its own container/IP — query *it*, not
  headscale. Give `portal-vpn-coredns` a known address on `portal.network`.
- **`SERVFAIL` externally:** DoT upstream unreachable; CoreDNS needs outbound
  `853/tcp`. `journalctl -u portal-vpn-coredns`.
- **Simplest option:** if the portal/Boundary FQDNs already resolve between your
  hosts, skip names and put IPs directly in `BROKER_TARGETS`.

---

## Quadlet / systemd

- **Unit missing after deploy:** `systemctl daemon-reload` (deploy.sh does this),
  then `systemctl status portal-<name>`. Generator errors:
  `journalctl -t quadlet-generator` or
  `/usr/libexec/podman/quadlet -dryrun` against the unit dir.
- **`Volume=X.volume` not found:** the reference is the **unit filename**
  (`headscale-data.volume`), not the `VolumeName=`.
- **netns share:** the broker uses `Network=container:portal-bastion-ts` — the
  bastion node must be **started first** (`After=`/`Requires=` handle this).
- **`Environment=` with spaces gets split** into separate vars — quote it:
  `Environment="TS_EXTRA_ARGS=--a --b"`.
- **`Memory=` is rejected** by the Quadlet generator (podman 5.4); use
  `PodmanArgs=--memory=…`.
- **Crash loop discipline:** every unit uses `Restart=on-failure` +
  `RestartSec` + `StartLimitBurst=5`, so a bad config degrades to a *stopped*
  service rather than pegging the host. If a unit is stopped, read its journal —
  don't just restart it.

## Leaks — false reachability

If a workstation can reach an internal host it should **not**, suspect network
routing, not a tailnet grant. In production the bastion is the only host bridging
the public and `portal.network` sides; verify no other route exists (firewall
matrix in the main README). To reproduce the airtight posture locally, the
HashiCorp access UAT uses an `internal: true` Podman network so sibling bridges
can't route to each other — see
[`../../../../integration-demos/hashicorp-stack/access/troubleshooting`](../../../../integration-demos/hashicorp-stack/access/troubleshooting).
