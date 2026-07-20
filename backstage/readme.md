# Backstage Dev Portal — HashiCorp-controlled, enterprise pattern

An internet-facing developer portal an end user can safely use to
browse and update internal dev projects. The portal itself publishes **no
port**: HashiCorp Boundary is the only way in, Keycloak owns user identity
(OIDC SSO), Vault owns every secret, TLS runs on every endpoint, and all
service-to-service traffic rides the Consul Connect mesh with
deny-by-default intentions. Dev projects are stored in Gitea.

```
                     internet user
                          |
                 boundary authenticate            Keycloak (OIDC SSO)
                 boundary connect                 https://127.0.0.1:28443
                 (brokered, audited TCP session)     ^  browser login +
                          |                          |  backchannel token
   +----------------- Boundary ------------------+   |  exchange
   |             (only published door)           |   |
   |                                             |   |
   |   dev-portal target          portal-postgres-dba target
   |   portal-proxy:8443 (TLS)    postgres:5432 (TLS) + Vault-brokered
   |        |                     10-minute read-only creds
   v        v                                    |
   portal-proxy (nginx TLS, path routing)        |
     /api/{catalog,search}/*  ->  Deployment B   |
     all other traffic        ->  Deployment A   |
        |                |                       |
   backstage-a      backstage-b   (same image, no published ports)
        \                /                       |
         \--- mesh -----/                        |
          Connect mTLS                           v
        +--> Postgres 18: one DBMS, TLS-only (hostssl+scram), per-plugin
        |                 logical databases (backstage_plugin_app/_auth/_catalog/...),
        |                 portal creds rotated by Vault
        +--> Gitea 1.27 (TLS): dev project storage — git repos with
                               catalog-info.yaml + org.yaml discovered over the mesh
```

This is the Backstage horizontal-scaling shape — split backend deployments
behind a path-routing reverse proxy, each plugin with its own logical
database on a shared Postgres DBMS. Both deployments run the same bundle
(the documented simple path); a production build could compile
per-deployment bundles containing only the routed plugins. The proxy stamps
`X-Portal-Deployment: a|b` on responses so routing stays observable.

| Concern | Owner |
|---|---|
| Ingress / who may reach what | Boundary (brokered sessions, per-target authz) |
| User identity / SSO | Keycloak realm `portal`, Backstage OIDC provider (`emailMatchingUserEntityProfileEmail` against the org model in Gitea) |
| Portal DB password | Vault database **static role** — fixed user `backstage`, password rotated by Vault, fetched at container start |
| DBA database access | Vault database **dynamic role** — 10-min `pg_read_all_data` users, brokered through Boundary |
| Gitea + OIDC client secrets | Vault **kv-v2** (`secret/gitea/portal`, `secret/oidc/portal`), read by the portal at start |
| Transport security | Stack CA (`portal-certs-init`) issues certs for nginx, Gitea, Keycloak, Consul, Boundary, and both Postgres instances (hostssl-only + scram); Connect adds mTLS between services; Vault runs its own TLS |
| Dev project storage | Gitea (SSH disabled, self-registration disabled, admin provisioned via CLI) |

## Quickstart

```bash
./run_portal.sh
```

Builds everything (the Backstage image build is long — it scaffolds and
compiles a full app), starts the stack, provisions Vault/Boundary/Gitea/
Keycloak, runs the UAT battery, and opens the end-user session. Requires
podman + podman-compose (or `COMPOSE="docker compose" RUNTIME=docker`).

**The portal UI**: https://127.0.0.1:27007 — this is a live Boundary session
published from the boundary container (`scripts/portal-session.sh` re-opens
it any time). Sign in with **Company SSO (Keycloak)** as `portal-dev` /
`PORTAL_DEV_PASSWORD` from `.env`, or use the demo guest button. The TLS
cert chains to the demo CA at `./.portal-ca.crt` — import it or accept the
browser warning.

Operator entry points (all TLS):

| Service | URL | Credentials |
|---|---|---|
| Consul UI | https://localhost:28500/ui | — |
| Vault UI | https://localhost:28200/ui | root token in the `portal-state` volume (`vault-init.json`) |
| Boundary API | https://localhost:29200 | admin login printed by the UAT battery |
| Keycloak | https://localhost:28443 | `admin` / `KC_ADMIN_PASSWORD` from `.env` |
| Gitea | https://localhost:23000 | `GITEA_ADMIN_USER` / `GITEA_ADMIN_PASSWORD` from `.env` |

DBA flow — Boundary injects a Vault-issued user that expires in 10 minutes;
the operator never sees a standing password:

```bash
boundary connect postgres -addr https://localhost:29200 \
    -target-id <db ttcp_...> -dbname backstage_plugin_catalog
```

## UAT / smoke tests

`./scripts/smoke-test.sh` (also run by `run_portal.sh`) verifies:

1. Consul (TLS API) has a leader; `vault`, `postgres`, `gitea`, `backstage`
   are in the catalog; intentions allow `backstage→postgres` and
   `backstage→gitea` and deny every other pair tested.
2. Vault is initialized/unsealed; the portal's static DB credential and the
   Gitea kv secret exist.
3. Gitea serves the seed dev project (`devteam/sample-service`) over TLS.
4. Both portal deployments are ready and booted with Vault-issued DB
   credentials; the per-plugin logical databases exist in Postgres; proxy
   path routing provably lands on the right deployment
   (`X-Portal-Deployment`); the catalog API (authenticated with the static
   UAT service token) contains the Gitea-hosted component; unauthenticated
   API calls get 401.
5. The org model (User `portal-dev`, Group `devteam`) is ingested; Keycloak
   publishes the expected issuer and actually issues tokens for
   `portal-dev`; the client secret in Vault kv matches Keycloak; Backstage's
   `/api/auth/oidc/start` redirects to Keycloak.
6. Boundary admin auth works; an end-user brokered session to the portal
   target serves the UI *and* the catalog API over TLS; a DBA session
   brokers Vault credentials that genuinely log in to Postgres and read
   catalog data.

Repo-level static validation (`pytest tests/` at the repo root) covers the
compose file, Dockerfile, and yaml hygiene for this directory.

## Layout

```
Dockerfile            production image (node 24): create-app scaffold ->
                      backend bundle, OIDC sign-in patch, non-root runtime;
                      entrypoint fetches Vault secrets at boot
patches/App.tsx       new-frontend-system sign-in page: Keycloak OIDC + guest
app-config.yaml       portal config (also baked into the frontend at build)
docker-compose.yml    full stack (no published portal port; TLS everywhere)
proxy/                nginx TLS + path routing to the split deployments
run_portal.sh         one-command bring-up + provisioning + UAT + session
consul/               server config: Connect + deny-by-default intentions,
                      TLS API, service + sidecar registrations
vault/                server config (raft, TLS, Consul registration)
boundary/             controller+worker config (TLS listeners, KMS from .env)
postgres/             init script (portal + keycloak roles) and TLS-only HBA
scripts/              gen-certs, vault/boundary/gitea/keycloak/idp setup,
                      portal-session, smoke-test
production-deploy/    podman Quadlet units, one role per VM, with per-role
                      host prep (sysctl/kernel) — the production path;
                      compose stays the local test rig (see its README)
troubleshooting/      incident-derived diagnostics + repair scripts
                      (status, portal diagnosis, migration-lock repair,
                      mesh check, vault secrets, boundary session debug,
                      offline diagnostics bundle — see its README)
archive/              previous k8s/python deployment (superseded)
```

## Troubleshooting

- **`MigrationLocked: Migration table is already locked` on portal boot** —
  a crashed boot stranded knex migration locks. Deployment B is gated on A
  being healthy precisely so fresh databases are migrated by one replica,
  but if you hit this (e.g. after killing containers mid-migration), stop
  the portal replicas and clear the locks:
  ```bash
  podman exec backstage-postgres sh -c '
    for db in $(psql -U pgadmin -d postgres -tAc "SELECT datname FROM pg_database WHERE datname LIKE '\''backstage%'\''"); do
      for t in $(psql -U pgadmin -d "$db" -tAc "SELECT tablename FROM pg_tables WHERE tablename LIKE '\''%knex_migrations_lock'\''"); do
        psql -U pgadmin -d "$db" -qc "DELETE FROM \"$t\" WHERE index NOT IN (SELECT min(index) FROM \"$t\")"
        psql -U pgadmin -d "$db" -qc "UPDATE \"$t\" SET is_locked=0"
      done
    done'
  ```
  (The `DELETE` also removes duplicate lock rows, which make the lock
  permanently unacquirable — knex expects exactly one row.)
- **Browser distrusts the portal/Keycloak/Gitea certs** — run
  `./troubleshooting/install-ca.sh` (Firefox can't import the hidden
  `.portal-ca.crt` from its file picker; the helper extracts a visible copy
  and installs it into Firefox's own NSS store via certutil, since Firefox
  ignores the system trust store). Or replace `scripts/gen-certs.sh` with
  your corporate PKI.

## Production notes

- The portal keeps a **guest** fallback button next to Keycloak SSO; remove
  it from `patches/App.tsx` and `app-config.yaml` for a strict SSO-only
  portal, and wire the Keycloak realm to your corporate IdP (LDAP/SAML
  federation) instead of the seeded demo user.
- The Vault token for the portal is periodic (72h). In production run a
  Vault Agent sidecar (auto-auth + template) instead of the entrypoint
  fetch, and re-run the setup provisioning from CI, not compose one-shots.
- Vault is initialized with 1 key share for the demo; use a real key
  ceremony and auto-unseal in production.
- Postgres backups: `pgbackup` runs a daily `pg_dumpall` (over TLS) into the
  `pg-backups` volume, pruned after 7 days.
- The bridge network is flat; the mesh enforces service identity, not L3
  isolation. In production bind services to localhost + sidecar only, or run
  on an orchestrator with NetworkPolicies (the archived k8s manifest shows
  the shape).
- The demo CA is a compose one-shot; swap `gen-certs.sh` for your PKI (or
  Vault's own PKI engine) and rotate certs out of band.
