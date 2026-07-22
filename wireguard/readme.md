# WireGuard gateway (site-to-site / egress)

A WireGuard tunnel gateway you deploy on a host so containers and remote sites
route to each other over an encrypted link, and clients can egress through it.
Driven by [`stack.yaml`](stack.yaml) and run three ways:

- **compose / rootless podman** for a local two-gateway demo ([`docker-compose.yml`](docker-compose.yml))
- **Podman Quadlet (systemd)** for a real gateway host ([`ansible/`](ansible))
- validated end-to-end by the **UAT** ([`uat/run-uat.sh`](uat/run-uat.sh))

> **Kernel module.** WireGuard is a kernel feature. Creating a `type wireguard`
> interface **auto-loads** the host `wireguard` module (no `modprobe`/sudo), so
> the UAT runs unprivileged; on `--down` it best-effort unloads the module if
> passwordless sudo is available. The Quadlet deploy loads it **persistently** on
> the target host (for reboots) and records how to revert.

## Configure

Edit [`stack.yaml`](stack.yaml):

```yaml
tunnel:
  site_b_addr: 10.9.0.2/24      # this gateway's tunnel address
  site_b_networks: 10.55.0.0/24 # LAN subnets reachable across the tunnel
peers:
  - public_key: "<client wg public key>"
    allowed_ips: "10.9.0.10/32"
```

Peer keys are generated at test/deploy time and never committed. The gateway's
own key is generated once by the deploy into `ansible/.secrets/` (gitignored).

## Run locally (two-gateway demo)

```bash
cd uat && ./run-uat.sh          # generates keys, loads the module, brings up both ends
```

## Deploy (Podman Quadlet)

```bash
cd ansible
ansible-playbook -i inventory.ini deploy.yml
```

Installs a `wireguard-gateway` Quadlet unit under `/etc/containers/systemd`,
renders `wg0.conf` from `stack.yaml`, publishes the WireGuard UDP port, and
manages the two host settings WireGuard needs:

- loads the `wireguard` module and persists it via
  `/etc/modules-load.d/wireguard.conf`
  (revert: remove that file and `modprobe -r wireguard`);
- enables `net.ipv4.ip_forward` via `/etc/sysctl.d/99-wireguard-gateway.conf`
  when the gateway routes onto a LAN (revert: remove that drop-in).

Set `manage_wireguard_module: false` / `manage_host_forwarding: false` in
`ansible/group_vars/all.yml` to skip either.

## Test

```bash
cd uat && ./run-uat.sh          # ./run-uat.sh --down to tear down and unload the module
```

The UAT generates both peer keypairs, loads the module, brings up two gateways,
and asserts: both create the kernel `wg0` interface, the handshake completes,
site-a reaches site-b across the tunnel (ping), encrypted bytes traverse it
(transfer counters), and a service on the far gateway is reachable over the
tunnel.