# SonarQube + Keycloak full stack

A complete, config-driven SonarQube environment with real Keycloak single
sign-on, tuned PostgreSQL, backups, a recursive code scanner, and both a
single-host (compose) and multi-VM (Ansible + Podman Quadlets) deployment.

```
browser ─TLS→ traefik ─┬─ forwardAuth → tinyauth ──OIDC──→ keycloak ── keycloak-db
                       ├──→ sonarqube (header SSO) ───────── sonar-db
                       └──→ keycloak (login UI)
 backups ── pg_dump → both databases
```

- **traefik** terminates TLS and is the only route to each app.
- **tinyauth** is the policy enforcement point and an OIDC relying party for
  **Keycloak** — the real identity provider. Users log in at Keycloak; on
  success traefik passes the identity to SonarQube as `Remote-User` and
  SonarQube signs them in (HTTP header SSO). One login, no local password.
- Each application has its own **PostgreSQL**, tuned for performance and
  longevity and locked to SCRAM-SHA-256 (`postgres/postgresql.conf`,
  `postgres/pg_hba.conf`).
- A **backup** sidecar `pg_dump`s both databases nightly.

Issuer host consistency: the whole stack is published on one `host:port`
(`127.0.0.1:8443`, with `TLS_PORT == 8443`) so the Keycloak issuer URL is
identical for the browser and for tinyauth's back-channel. tinyauth resolves
that host to traefik and trusts the stack CA via `SSL_CERT_FILE`.

## One source of truth: `stack.yaml`

Hosts, images, the Keycloak realm/users, secrets and scan paths all live in
[`stack.yaml`](stack.yaml). It feeds every part of the system:

| Consumer | Uses |
| --- | --- |
| `scripts/render.sh` | renders `.env`, `tinyauth.env`, `keycloak/realm-sonar.json` |
| `scripts/scan.sh` | reads `scan.paths`, `scan.server`, `scan.token` |
| `ansible/` | reads it as vars for the multi-VM deployment |

Blank `secrets:` are generated once and written to the gitignored `.env` /
`tinyauth.env`; re-running `render.sh` reuses them.

## Run it (single host, compose)

```sh
cd uat && ./run-uat.sh          # generate TLS + config, bring up, smoke test
cd uat && ./run-uat.sh --down   # tear down
```

The smoke test brings the whole stack up over TLS and asserts **build →
Keycloak login → SonarQube session**: it drives the OIDC authorization-code
flow (submitting the demo user's credentials to Keycloak's login form),
confirms tinyauth issues a session, and confirms SonarQube reports the
Keycloak user as an external (non-local) login. It also checks the gate
rejects unauthenticated and spoofed-header requests.

For a non-UAT deployment, render the artifacts from `stack.yaml` and bring
the project up yourself:

```sh
scripts/render.sh                                   # .env, tinyauth.env, realm
# place real tls.crt / tls.key / ca.crt in stack.tls_dir
podman-compose --env-file .env -f docker-compose.yml up -d
```

## Scan codebases

`scripts/scan.sh` runs SonarScanner over one or more codebases and submits
the analyses. Paths come from the command line or `scan.paths` in
`stack.yaml`; `--recursive` discovers every project root (a directory with a
build marker) beneath each path.

```sh
# generate an analysis token in SonarQube (My Account → Security), then:
SONAR_HOST_URL=https://sonarqube.example.com:8443 SONAR_TOKEN=squ_xxx \
  scripts/scan.sh --recursive /srv/code
```

Scanner traffic uses the token and takes the proxy's machine-bypass route,
so it authenticates without an interactive login. For a private CA over TLS,
pass a PKCS12 truststore via `SONAR_TRUSTSTORE`; for internal access, join
the container network with `SONAR_NETWORK`.

## Deploy across VMs (Ansible + Quadlets)

`ansible/` deploys one service per VM as Podman **Quadlet** systemd units —
the production answer for rootful hosts (survives reboot, systemd-managed).
Set `container_runtime: docker` to skip Quadlets and use the single-host
compose file instead.

```sh
cd ansible
# edit inventory.ini with your VM addresses (match stack.yaml vms:)
# put tls.crt / tls.key / ca.crt in ansible/files/tls/
ansible-playbook -i inventory.ini deploy.yml
```

Each group (`proxy`, `keycloak`, `keycloak_db`, `sonarqube`, `sonar_db`)
gets its service; the proxy VM also runs tinyauth. Traefik uses the file
provider to route to each service by its VM address. Secrets are generated
once on the controller under `ansible/.secrets/` (gitignored). Lint with
`ci/ansible-lint.sh` (passes at the production profile).
