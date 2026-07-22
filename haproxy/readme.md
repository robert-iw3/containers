# HAProxy reverse proxy

A configurable TLS reverse proxy you drop in front of any backend application
stack. Routing is defined by a simple `routes:` list in [`stack.yaml`](stack.yaml).
The same config runs three ways:

- **compose / rootless podman** for local use ([`docker-compose.yml`](docker-compose.yml))
- **Podman Quadlet (systemd)** for hosts ([`ansible/`](ansible))
- and is validated end-to-end by the **UAT** ([`uat/run-uat.sh`](uat/run-uat.sh))

HAProxy terminates TLS and load-balances to your backend. The bundled `whoami`
service stands in for "any backend" so the stack works out of the box.

## Configure

Edit `routes:` in [`stack.yaml`](stack.yaml):

```yaml
routes:
  - host: app.example.com     # Host header to match (port-insensitive)
    upstream: backend:8080    # any reachable host:port
```

The compose path uses the concrete demo routing in
[`config/haproxy.cfg`](config/haproxy.cfg); the Quadlet deployment renders the
equivalent from `routes:` via [`ansible/templates/haproxy.cfg.j2`](ansible/templates/haproxy.cfg.j2)
(one host ACL + backend per route). HAProxy binds high ports (8080/8443) inside
the container so it runs as the non-root `haproxy` user; they are published to
the host.

## Run locally

```bash
cp .env.example .env
# put a haproxy.pem (cert+key) into ./uat/tls, or run the UAT once to generate it
podman-compose up -d
curl --cacert uat/tls/ca.crt --resolve app.localhost:8443:127.0.0.1 \
     https://app.localhost:8443/
```

## Deploy (Podman Quadlet)

```bash
cd ansible
# drop haproxy.pem into files/tls (see files/tls/README.md)
ansible-playbook -i inventory.ini deploy.yml
```

Installs a `haproxy.network` + `haproxy.container` Quadlet unit under
`/etc/containers/systemd`, rendering `haproxy.cfg` from `stack.yaml`. Set
`bind_addr: 0.0.0.0` in `stack.yaml` to publish beyond loopback.

## Test

```bash
cd uat && ./run-uat.sh          # bring up + assert; ./run-uat.sh --down to clean up
```

The UAT generates a local CA, brings up the proxy + demo backend, and asserts a
real request traverses TLS to the backend, that `X-Forwarded-Proto` and security
headers are set, that HTTP redirects to HTTPS, and that an unknown Host gets no
route (404).