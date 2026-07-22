# Tailscale (self-hosted, offline)

A fully self-hosted Tailscale mesh VPN: [headscale](https://headscale.net) is the
control server and `tailscale` nodes join it — **no Tailscale SaaS, no public
coordinator, no auth key from the internet**. One node acts as a **subnet router
+ exit node** so containers and hosts route site-to-site and send their egress
through the tunnel. Everything is driven by [`stack.yaml`](stack.yaml) and runs
three ways:

- **compose / rootless podman** for local use ([`docker-compose.yml`](docker-compose.yml))
- **Podman Quadlet (systemd)** for hosts ([`ansible/`](ansible))
- validated end-to-end by the **UAT** ([`uat/run-uat.sh`](uat/run-uat.sh))

Nodes run in **userspace / netstack mode** — no `/dev/net/tun`, no kernel
WireGuard module, no host changes.

## Configure

Edit [`stack.yaml`](stack.yaml):

```yaml
advertise_routes: 10.55.0.0/24   # subnet the router exposes (site-to-site)
advertise_exit_node: true        # also offer egress-through-the-tunnel
stack:
  hs_ip: 172.30.9.2              # static IP nodes use for the control server
```

Headscale settings live in [`config/config.yaml`](config/config.yaml) (compose)
and [`ansible/templates/config.yaml.j2`](ansible/templates/config.yaml.j2)
(Quadlet). The one value to change per environment is `server_url`.

## Run locally

```bash
podman-compose up -d headscale
podman exec headscale headscale users create uatuser
podman exec headscale headscale preauthkeys create --user 1 --reusable --expiration 24h
# put the key in .env as TS_AUTHKEY, then:
podman-compose up -d node-a node-b
podman exec headscale headscale nodes list
```

## Deploy (Podman Quadlet)

```bash
cd ansible
ansible-playbook -i inventory.ini deploy.yml
```

Installs `tailscale.network`, a `headscale.volume`, the `headscale` control
server and a `tailscale-router` node as Quadlet units under
`/etc/containers/systemd`. The playbook mints the router's pre-auth key from the
freshly deployed headscale (written to `/etc/headscale/router.env`, mode 0600).
Point other members at the control server with
`--login-server=http://<host>:8080`.

## Test

```bash
cd uat && ./run-uat.sh          # bring up + assert; ./run-uat.sh --down to clean up
```

The UAT stands up headscale, mints a pre-auth key, joins two nodes, and asserts
both get `100.64.x` tailnet addresses, node-a reaches node-b over the tailnet
(`tailscale ping` → pong), headscale shows both registered, and the gateway
advertises the site-to-site subnet route and an exit node.