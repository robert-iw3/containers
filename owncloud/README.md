# ownCloud — production stack

Enterprise-oriented ownCloud deployment, end to end. Two server lines are
covered:

- **Classic ownCloud 10.x** (PHP, MariaDB) — this directory. Mature, huge
  app ecosystem, drop-in for existing 10.x installs.
- **ownCloud Infinite Scale (oCIS)** (Go, no PHP/DB) — [ocis/](ocis/). The
  next-generation server; far lighter to operate, but a different product
  with its own migration path. Run one or the other, not both.

| Path | What it is |
|---|---|
| [Dockerfile](Dockerfile) | Hardened wrapper over `owncloud/server` (pinned version, healthcheck, OCI labels) |
| [docker-compose.yml](docker-compose.yml) | Full stack: Traefik (TLS) → ownCloud, MariaDB 10.11, Redis 7, scheduled backups |
| [ocis/](ocis/) | Infinite Scale alternative (Traefik + single oCIS service) |
| [kubernetes/](kubernetes/) | Single-file manifest set (StatefulSet MariaDB, Redis, app, Ingress) |
| [authelia/](authelia/) + [docker-compose.sso.yml](docker-compose.sso.yml) | Authelia SSO: OIDC provider for ownCloud + dashboard forward-auth (`--profile sso`) |
| [troubleshooting/](troubleshooting/) | Operational diagnostics (stack health, socket, socket-proxy, occ, OIDC) |
| `owncloud-backup.sh` / `owncloud-restore-*.sh` | Consistent on-demand backup and interactive restore |
| `owncloud-configure-oidc.sh` | Installs/configures the `openidconnect` Authelia provider in ownCloud |

## Architecture (compose)

```
Internet ──443──> Traefik (Let's Encrypt, HSTS, security headers)
                    └──> ownCloud :8080 (built-in web server + internal cron)
                           ├──> MariaDB 10.11  (internal network only)
                           └──> Redis 7        (locking + caching, password-protected)
   backups — scheduled mariadb-dump + /mnt/data archive with retention pruning
```

The database and cache live on an `internal: true` network with no
host-published ports and no outbound routing. Only Traefik listens on the
host. ownCloud's background jobs run via the image's internal cron
(`OWNCLOUD_BACKGROUND_MODE=cron`) — no separate cron container needed.

## Quick start

```sh
cd owncloud
cp .env.example .env        # fill in EVERY value; openssl rand -base64 32 for secrets
docker compose up -d --build
```

DNS for `OWNCLOUD_HOSTNAME` (and `TRAEFIK_HOSTNAME`) must point at the host
before first start so the TLS-ALPN challenge can complete. First boot takes a
couple of minutes while the entrypoint installs and migrates; watch it with
`docker logs -f owncloud-app`.

Podman works too: `podman compose up -d --build` (mount the podman socket for
Traefik: `$XDG_RUNTIME_DIR/podman/podman.sock:/var/run/docker.sock:ro`).

## First-run checklist

After the stack is healthy (`docker compose ps`):

```sh
# Verify install status and background job mode
docker exec owncloud-app occ status
docker exec owncloud-app occ background:queue:status

# Check the security/setup warnings
docker exec owncloud-app occ security:routes   # optional audit
```

Then log in as `OWNCLOUD_ADMIN_USERNAME` and review
**Settings → Admin → General** — the setup checks should pass (proxy headers
and `overwrite.cli.url` are preconfigured via `OWNCLOUD_DOMAIN` /
`OWNCLOUD_PROTOCOL`).

## Backups

Two layers:

1. **Scheduled** — the `backups` sidecar runs `mariadb-dump
   --single-transaction` and archives `/mnt/data` every `BACKUP_INTERVAL`
   (default 24 h), pruning after `BACKUP_RETENTION_DAYS` (default 7).
   Archives land in the `owncloud-db-backups` / `owncloud-data-backups`
   volumes.
2. **On-demand, application-consistent** — `./owncloud-backup.sh` flips
   maintenance mode on, dumps DB + files, and flips it back off. Use this
   before upgrades.

Restore interactively with `./owncloud-restore-database.sh` and
`./owncloud-restore-files.sh`.

Ship the backup volumes off-host (e.g. restic/borg to S3) — a local copy is
not a disaster-recovery plan.

## Upgrades

1. `./owncloud-backup.sh`
2. Bump `owncloud_version` in the [Dockerfile](Dockerfile) — step through
   minor releases in order; never skip a major version.
3. `docker compose build && docker compose up -d` — the entrypoint runs
   `occ upgrade` automatically on version change.
4. `docker exec owncloud-app occ status` to confirm, then re-check the admin
   overview page.

## Scaling & tuning

- **Object storage**: for large installs move primary storage to S3 with the
  `objectstore` app (`OBJECTSTORE_TYPE=s3` plus `OWNCLOUD_OBJECTSTORE_*`
  settings, or configure via `occ`).
- **Horizontal scale**: keep locking/sessions in Redis (already configured),
  move files to NFS or S3, and run multiple app containers behind Traefik —
  or use [kubernetes/](kubernetes/) with a ReadWriteMany PVC.
- **MariaDB**: `--max-allowed-packet=128M` is preset; size the buffer pool
  (`--innodb-buffer-pool-size`) to ~60% of the DB host's RAM for dedicated
  hosts.
- **Considering oCIS?** No PHP, no SQL database, built-in IdP, ~10× less
  memory per user. See [ocis/](ocis/) — note it is a migration, not an
  in-place upgrade.

## Kubernetes

```sh
# Edit kubernetes/owncloud-k8s.yaml: Secret values, hostnames, storage sizes
kubectl apply -f kubernetes/owncloud-k8s.yaml
```

Assumes ingress-nginx + cert-manager (`ClusterIssuer/letsencrypt`). Replace
the inline `Secret` with SealedSecrets/ExternalSecrets in real environments.

## Single sign-on (Authelia)

The `sso` profile adds [Authelia](authelia/) as an **OpenID Connect provider**
for ownCloud (SSO on the web login via the `openidconnect` app) and as
**forward-auth** for the Traefik dashboard. Sync/mobile/DAV clients keep working
with app passwords — which is why OIDC is used rather than forward-auth in front
of ownCloud (that would break every non-browser client).

```
Browser ── https://owncloud ──► Traefik ──► ownCloud ──redirect──► Authelia (login)
                                                 ▲                      │
      back-channel (discovery/token/JWKS) ───────┴──────────────────────┘
Browser ── https://traefik  ──► Traefik ──forward-auth──► Authelia
```

Setup:

```sh
# 1. Bootstrap Authelia secrets and the login user (see authelia/README.md)
#    -> creates authelia/secrets/* (git-ignored)
# 2. Fill the SSO block in .env (hostnames, OIDC client id/secret + its hash)
# 3. Bring the stack up WITH the overlay and profile
docker compose -f docker-compose.yml -f docker-compose.sso.yml \
  --profile sso up -d
# 4. Install + configure the ownCloud openidconnect app
./owncloud-configure-oidc.sh
```

The overlay ([docker-compose.sso.yml](docker-compose.sso.yml)) adds a Traefik
alias for the Authelia hostname so the OIDC issuer URL resolves from the app
container (the ownCloud app already sits on the frontend network). In production
Traefik serves a valid ACME certificate, so the app trusts the issuer with no
extra configuration. Note ownCloud's `openidconnect` app authenticates to the
token endpoint with `client_secret_basic` (the Authelia client is configured to
match). Set `TRAEFIK_DASHBOARD_MIDDLEWARE=authelia-fwd@docker` to move the
dashboard from basic-auth to Authelia forward-auth.

## Security notes

- Version-pinned images; all containers run with `no-new-privileges`.
- DB/cache unreachable from the host network (internal-only bridge).
- Traefik reaches the container engine through a filtered, read-only
  [socket proxy](docker-compose.yml) on an isolated network — it never mounts
  the raw socket.
- Traefik dashboard requires basic auth (bcrypt), or Authelia forward-auth
  with the `sso` profile.
- Authelia secrets live in `authelia/secrets/` (git-ignored); the committed
  `configuration.yml` is secret-free and pulls them via `AUTHELIA_*_FILE`.
- HSTS, nosniff, referrer-policy and robots headers applied at the proxy.
- Rotate `.env` secrets through your secret manager; `.env` is git-ignored.
- For host tuning (sysctls, file limits, firewall) reuse
  [../nextcloud/host-prep/prepare-host.sh](../nextcloud/host-prep/prepare-host.sh).
