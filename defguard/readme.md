# Defguard VPN (WireGuard management)

A self-hosted WireGuard VPN with a real control plane: Defguard **core** (web
UI, REST API, user/device management) drives a WireGuard **gateway** over an
authenticated gRPC channel, with postgres behind it. Driven by
[`stack.yaml`](stack.yaml) and run three ways:

- **compose / rootless podman** for local use ([`docker-compose.yml`](docker-compose.yml))
- **Podman Quadlet (systemd)** for hosts ([`ansible/`](ansible))
- validated end-to-end by the **UAT** ([`uat/run-uat.sh`](uat/run-uat.sh))

Pinned to the **1.4.0 core+gateway pair** — defguard's production release
channel, validated here end-to-end (see *Upgrading to 2.x* below before
bumping).

## Stability by construction

This stack has crashed a machine once, so the guardrails are explicit:

- **compose**: core and gateway use `restart: on-failure:5` — podman applies
  **no backoff** between restarts, so an early-exit bug under `unless-stopped`
  becomes an unthrottled crash loop. Bounded means it stops and waits for a
  human. Memory is capped per service (`mem_limit`).
- **Quadlet**: systemd throttling on every unit — `RestartSec` plus
  `StartLimitIntervalSec=120` / `StartLimitBurst=5`, so a bad config degrades to
  a stopped service, never a loop.
- **UAT**: `ensure_stable` gates every stage — a container that exits early or
  restart-loops is **stopped**, its logs dumped, and the test fails fast.

## Run locally

```bash
cd uat && ./run-uat.sh        # brings everything up with generated secrets
```

or by hand: `cp .env.example .env`, replace every `CHANGE_ME`, then
`podman-compose up -d db core`. Once core is healthy, create a network in the
UI (http://localhost:8000), copy its gateway token into `.env` as
`DEFGUARD_TOKEN`, and `podman-compose up -d gateway`.

## Deploy (Podman Quadlet)

```bash
cd ansible
ansible-playbook -i inventory.ini deploy.yml
```

Installs `defguard.network`, a `defguard-db` volume+container, `defguard-core`
and `defguard-gateway` as Quadlet units under `/etc/containers/systemd`.
The playbook waits for core, **provisions the VPN network through the real
API**, mints the gateway token (persisted once at `/etc/defguard/gateway.env`,
mode 0600), starts the gateway, and verifies core reports it *connected*.
Secrets generate once into `ansible/.secrets/` (gitignored). The wireguard
kernel module is persisted for reboots via `/etc/modules-load.d/wireguard.conf`
(revert: remove that file).

Add VPN users/devices in the core UI; peers connect to the gateway's published
UDP port (`51820`).

## Test

```bash
cd uat && ./run-uat.sh          # ./run-uat.sh --down to tear down
```

Asserts: db healthy → core healthy → admin authenticates → VPN network
provisioned via API → gateway token minted → **gateway connects to core over
gRPC** (core reports `connected: true`) → gateway brings up the kernel
WireGuard interface (`wg0`).

## Upgrading to 2.x

Defguard 2.0 (July 2026) is a different provisioning architecture: no
`DEFGUARD_DEFAULT_ADMIN_PASSWORD` — first boot serves an **initial-setup
wizard**, and gateways join through a new **adopt** flow instead of the
network-token endpoint. The wizard *is* scriptable against
`/api/v1/initial_setup/*`, validated in this repo's testing:

1. `POST /admin` `{first_name,last_name,username,email,password}` → 201
2. `POST /login` `{username,password}` → session cookie
3. `POST /ca` `{common_name,email,validity_period_years}` → 201 (mandatory —
   finishing without it leaves core unbootable)
4. `POST /general_config` `{default_admin_group_name,default_authentication,
   default_mfa_code_lifetime}` → 201 — `default_authentication` is the session
   validity in **days**; 0 makes every login expire instantly
5. `POST /finish` → 200, core restarts into normal mode

The 2.x network schema adds `mtu`, `fwmark`, `allow_all_groups`,
`location_mfa_mode`/`service_location_mode` (`"disabled"`), and the gateway
adopt-token flow replaces `GET /network/{id}/token`. Migrate when the 2.x adopt
flow is documented upstream; bump `core_image` and `gateway_image` **together**.