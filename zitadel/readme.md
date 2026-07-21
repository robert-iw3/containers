# ZITADEL

[![zitadel](https://img.youtube.com/vi/S98SAXgRpOM/0.jpg)](https://www.youtube.com/watch?v=S98SAXgRpOM)

Identity and access management platform. This stack runs ZITADEL v4 on
PostgreSQL with the v2 login app and traefik, based on the upstream
compose bundle (`deploy/compose`, Apache-2.0) with local hardening:
`no-new-privileges`, log rotation, fully-qualified pinned images and a
parameterized container-runtime socket.

> ZITADEL v3 dropped CockroachDB support; everything under `crdb/` and
> `config/` targets the old CockroachDB-based v2 stack and is kept for
> reference only.

## Deploy

```bash
cp .env.example .env
# set ZITADEL_MASTERKEY (exactly 32 chars), POSTGRES_ADMIN_PASSWORD and
# the matching ZITADEL_DATABASE_POSTGRES_DSN, plus your domain settings
podman-compose up -d postgres
podman-compose up -d zitadel-api
podman-compose up -d zitadel-login proxy
```

Services:
- `proxy` — traefik, publishes `${PROXY_HTTP_PUBLISHED_PORT}` (TLS modes
  are available in the upstream bundle's overlay files)
- `zitadel-api` — ZITADEL core, h2c behind traefik, `/app/zitadel ready`
  healthcheck
- `zitadel-login` — the v2 login UI, bootstrapped via a service-account
  PAT that `zitadel-api` writes to the shared `zitadel-bootstrap` volume
- `postgres` — pinned official image, no published ports
- optional profiles: `cache` (redis), `observability` (otel-collector)

First instance admin: `zitadel-admin@zitadel.localhost` with password
`Password1!` (password change not enforced — rotate immediately).

## Smoke test / UAT

```bash
./uat/run-uat.sh        # TLS ZITADEL on https://localhost:8443 + mock OIDC app
./uat/run-uat.sh --down # tear down
```
The UAT generates a local CA, terminates TLS with an nginx front that
route-splits the API and the v2 login UI, bootstraps a machine-user PAT,
creates a project + OIDC web application through the management API,
then runs a **mock relying application** (oauth2-proxy + `whoami`) that
completes the OIDC authorization-code flow against ZITADEL. Prints the
console and mock-app URLs with credentials.

## Deploy with Ansible

Each stack ships an Ansible deploy playbook (`ansible/deploy.yml`) that
brings the stack up via podman-compose:

```bash
cd zitadel/ansible
ansible-playbook -i inventory.ini deploy.yml
```
It seeds `.env` from `.env.example` on first run — set the masterkey, DB password and DSN first.
Validate playbook syntax with ansible-lint (run from a container, no host
install needed) from the repo root:

```bash
ci/ansible-lint.sh
```
