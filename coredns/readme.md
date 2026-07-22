# CoreDNS secure resolver

A hardened DNS resolver any container host can point at. It forwards recursive
queries over **DNS-over-TLS** (so lookups leaving the host are encrypted),
restricts who may query with an **ACL**, serves **authoritative internal names**,
and can offer **DoT to its own clients** on `:853`. Everything is driven by
[`stack.yaml`](stack.yaml). The same config runs three ways:

- **compose / rootless podman** for local use ([`docker-compose.yml`](docker-compose.yml))
- **Podman Quadlet (systemd)** with host networking ([`ansible/`](ansible))
- and is validated end-to-end by the **UAT** ([`uat/run-uat.sh`](uat/run-uat.sh))

## Configure

Edit [`stack.yaml`](stack.yaml):

```yaml
upstreams:   [ tls://9.9.9.9, tls://149.112.112.112 ]  # DoT upstreams (Quad9)
tls_servername: dns.quad9.net
acl_allow:   [ 172.28.10.0/24, 10.0.0.0/8 ]            # who may query
local_records:
  - { name: backend.svc.internal, ip: 10.0.50.20 }     # authoritative names
dot_listener: true                                      # serve DoT on :853
```

The compose path uses the concrete demo in [`config/Corefile`](config/Corefile);
the Quadlet deployment renders the equivalent from `stack.yaml` via
[`ansible/templates/Corefile.j2`](ansible/templates/Corefile.j2).

## Run locally

```bash
cp .env.example .env   # optional; the UAT generates its own
podman-compose up -d coredns
dig @127.0.0.1 -p 1053 backend.svc.internal
```

## Deploy (Podman Quadlet)

```bash
cd ansible
# drop tls.crt / tls.key into files/tls (see files/tls/README.md) for DoT
ansible-playbook -i inventory.ini deploy.yml
```

Installs a `coredns.container` Quadlet unit with **host networking** under
`/etc/containers/systemd`, so containers and the host resolve through it on
`:53`. To also repoint the host's own resolver at CoreDNS (disruptive — disables
the systemd-resolved stub and frees `:53`):

```bash
ansible-playbook -i inventory.ini deploy.yml -e configure_host_dns=true
```

## Test

```bash
cd uat && ./run-uat.sh          # bring up + assert; ./run-uat.sh --down to clean up
```

The UAT brings up CoreDNS plus two client containers on different subnets and
asserts: an internal name resolves to its record, an external name resolves
through the DoT upstream, a query from **outside** the ACL is `REFUSED` while an
allowed one is served, and the `:853` DoT listener answers over a certificate
the client verifies. (Needs outbound `853/tcp` to Quad9.)