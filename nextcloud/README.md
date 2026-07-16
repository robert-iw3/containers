# Nextcloud — production stack

Enterprise-oriented Nextcloud deployment, end to end:

| Path | What it is |
|---|---|
| [Dockerfile](Dockerfile) | Hardened php-fpm image built from the GPG-verified upstream tarball, digest-pinned base |
| [docker-compose.yml](docker-compose.yml) | Full stack: Traefik (TLS) → nginx → php-fpm, PostgreSQL 16, Redis 7, cron, scheduled backups |
| [config/](config/) | Config snippets baked into the image (Redis, APCu, reverse proxy, SMTP, S3 object store) |
| [nginx/nginx.conf](nginx/nginx.conf) | Upstream-recommended nginx config for the fpm split |
| [kubernetes/](kubernetes/) | Single-file manifest set (StatefulSet Postgres, Redis, app, CronJob, Ingress) |
| [terraform/](terraform/) | AWS reference deployment (VPC, RDS, ElastiCache, ALB/NLB, ACM, KMS, S3) |
| [authelia/](authelia/) + [docker-compose.sso.yml](docker-compose.sso.yml) | Authelia SSO: OIDC provider for Nextcloud + dashboard forward-auth (`--profile sso`) |
| [host-prep/](host-prep/) | Host sysctl/firewall/runtime preparation script |
| `nextcloud-backup.sh` / `nextcloud-restore-*.sh` | Consistent on-demand backup and interactive restore |
| `nextcloud-configure-oidc.sh` | Installs/registers the `user_oidc` Authelia provider in Nextcloud |

## Architecture (compose)

```
Internet ──443──> Traefik (Let's Encrypt, HSTS, security headers)
                    └──> nginx :8080 (static files, fastcgi)
                           └──> php-fpm (local hardened image)
                                  ├──> PostgreSQL 16  (internal network only)
                                  └──> Redis 7        (locking + caching, password-protected)
   cron    — dedicated container, busybox crond → cron.php every 5 min
   backups — scheduled pg_dump + data archive with retention pruning
```

The database and cache live on an `internal: true` network with no host-published
ports and no outbound routing. Only Traefik listens on the host.

## Quick start

```sh
cd nextcloud
cp .env.example .env        # fill in EVERY value; openssl rand -base64 32 for secrets
sudo ./host-prep/prepare-host.sh   # optional: sysctl/firewall tuning on fresh hosts
docker compose up -d --build
```

DNS for `NEXTCLOUD_HOSTNAME` (and `TRAEFIK_HOSTNAME`) must point at the host
before first start so the TLS-ALPN challenge can complete.

Optional components:

```sh
docker compose --profile office   up -d   # Collabora Online
docker compose --profile previews up -d   # Imaginary preview generation
```

Single sign-on (Authelia) has its own overlay and setup — see
[Single sign-on](#single-sign-on-authelia) below.

Podman works too: `podman compose up -d --build` (mount the podman socket for
Traefik: `$XDG_RUNTIME_DIR/podman/podman.sock:/var/run/docker.sock:ro`).

## First-run checklist

After the stack is healthy (`docker compose ps` — everything `healthy`):

```sh
# Background jobs via cron container (required — AJAX mode is not production-safe)
docker exec -u www-data nextcloud-app php occ background:job:mode cron

# Add missing DB indices/columns that first install can skip
docker exec -u www-data nextcloud-app php occ db:add-missing-indices
docker exec -u www-data nextcloud-app php occ maintenance:repair --include-expensive

# Set default phone region (admin-check requirement)
docker exec -u www-data nextcloud-app php occ config:system:set default_phone_region --value=US
```

Then open `https://<host>/settings/admin/overview` — the security & setup
checks should all pass.

## Backups

Two layers:

1. **Scheduled** — the `backups` sidecar dumps PostgreSQL and archives
   `/var/www/html` every `BACKUP_INTERVAL` (default 24 h), pruning after
   `BACKUP_RETENTION_DAYS` (default 7). Archives land in the
   `nextcloud-db-backups` / `nextcloud-data-backups` volumes.
2. **On-demand, application-consistent** — `./nextcloud-backup.sh` flips
   maintenance mode on, dumps DB + data, and flips it back off. Use this
   before upgrades.

Restore interactively with `./nextcloud-restore-database.sh` and
`./nextcloud-restore-application-data.sh`.

Ship the backup volumes off-host (e.g. restic/borg to S3) — a local copy is
not a disaster-recovery plan.

## Upgrades

The image owns the code (`upgrade.disable-web` is enforced), so upgrades are
image deployments:

1. `./nextcloud-backup.sh`
2. Bump `NEXTCLOUD_VERSION` in the [Dockerfile](Dockerfile) — **one major
   version at a time** (34 → 35 → 36; never skip).
3. `docker compose build && docker compose up -d` — the entrypoint runs
   `occ upgrade` automatically, keeping `config/`, `data/`, `custom_apps/`
   and themes (see [upgrade.exclude](upgrade.exclude)).
4. Re-run the first-run checklist commands (`db:add-missing-indices`, repair).

## Scaling & tuning

- **php-fpm**: defaults are conservative. For heavier fleets raise
  `pm.max_children` via an fpm pool override and `PHP_MEMORY_LIMIT` in `.env`.
- **Object storage**: set the `OBJECTSTORE_S3_*` variables (see
  [config/s3.config.php](config/s3.config.php)) to use S3 as primary storage —
  strongly recommended past a few hundred users, and what the
  [terraform/](terraform/) deployment assumes.
- **Previews**: enable the `previews` profile and point Nextcloud at it:
  `occ config:system:set preview_imaginary_url --value=http://imaginary:9000`,
  then add `\OC\Preview\Imaginary` to `enabledPreviewProviders`.
- **Horizontal scale**: keep sessions/locking in Redis (already configured),
  move data to S3, put multiple `web`+`nextcloud` pairs behind Traefik or use
  the [kubernetes/](kubernetes/) manifests with a ReadWriteMany PVC.

## Kubernetes

```sh
# Edit kubernetes/nextcloud-k8s.yaml: Secret values, hostnames, storage sizes
kubectl apply -f kubernetes/nextcloud-k8s.yaml
```

Assumes ingress-nginx + cert-manager (`ClusterIssuer/letsencrypt`). Replace the
inline `Secret` with SealedSecrets/ExternalSecrets in real environments. Cron
runs as a `CronJob` every 5 minutes.

## Single sign-on (Authelia)

The `sso` profile adds [Authelia](authelia/) as an **OpenID Connect provider**
for Nextcloud (real SSO on the web login via the `user_oidc` app) and as
**forward-auth** for the Traefik dashboard. Desktop, mobile and CalDAV/CardDAV
clients are unaffected — they keep authenticating with app passwords, which is
exactly why OIDC is used here instead of forward-auth in front of Nextcloud
(forward-auth would break every non-browser client).

```
Browser ── https://nextcloud ──► Traefik ──► Nextcloud ──redirect──► Authelia (login)
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
  --profile sso up -d --build

# 4. Register the provider inside Nextcloud (installs + configures user_oidc)
./nextcloud-configure-oidc.sh
```

The overlay ([docker-compose.sso.yml](docker-compose.sso.yml)) exists because
the app container is otherwise on the internal-only network; it gives Nextcloud
a route to the OIDC issuer (Traefik) so the back-channel calls resolve. In
production Traefik serves a valid ACME certificate, so the app trusts the
issuer with no extra configuration.

Setting `TRAEFIK_DASHBOARD_MIDDLEWARE=authelia-fwd@docker` in `.env` swaps the
dashboard from basic-auth to Authelia forward-auth. Leave it unset to keep
basic-auth (and Authelia purely as the Nextcloud IdP).

## AWS (Terraform)

[terraform/](terraform/) provisions a full AWS reference architecture: VPC,
public/private subnets, RDS PostgreSQL, ElastiCache Redis, EC2 + EBS, ALB/NLB
with ACM certificates, Route 53, KMS-encrypted S3 buckets and DynamoDB state
locking. See the workflow examples under `terraform/.github/`.