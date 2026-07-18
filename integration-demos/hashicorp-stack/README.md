# HashiCorp Stack — end-to-end integration demo

**Use case:** an operator (or service) needs access to a production PostgreSQL
database, but nobody should ever hold a standing database password.

- **Boundary** is the front door: users authenticate to Boundary, never to the
  database. When a session to the `postgres-appdb` target is authorized,
  Boundary pulls a **fresh, short-lived credential from Vault** (database
  secrets engine, 10-minute TTL) and brokers it into the session.
- **Vault** owns the secrets lifecycle: it creates a brand-new PostgreSQL role
  per request and expires it automatically.
- **Consul** is the service mesh and catalog: the app tier (`demo-api`)
  reaches PostgreSQL **only through Connect sidecars (mTLS)**, and
  **intentions** allow `demo-api → postgres-app` while denying everyone else.
  Vault registers itself in the catalog too.

```
                        ┌───────────────┐
   operator ──auth──►   │   BOUNDARY    │──── pulls dynamic creds ────┐
   (UI/CLI :19200)      │ controller +  │                             ▼
        │               │    worker     │                      ┌────────────┐
        │ session       └──────┬────────┘                      │   VAULT    │
        ▼ (:19202)             │ proxies session               │  database  │
   psql with Vault             ▼                               │   engine   │
   creds injected      ┌───────────────┐   creates/expires     └─────┬──────┘
                       │ postgres-app  │◄──── dynamic roles ─────────┘
                       └───────▲───────┘                             │
                               │ mTLS (Connect)              registers in
                       ┌───────┴────────┐                    ┌───────▼──────┐
                       │postgres-sidecar│◄───intentions────  │    CONSUL    │
                       └───────▲────────┘   allow demo-api   │ mesh+catalog │
                               │ mTLS       deny *           └───────▲──────┘
                       ┌───────┴───────┐                             │
   curl :18080 ──────► │  demo-api +   │────── fetches its own ──────┘
                       │  api-sidecar  │       Vault creds per request
                       └───────────────┘
```

## Run it

```bash
./run_demo.sh          # generates .env, builds, starts, configures, smoke-tests
```

Entry points once green:

| What | Where | Login |
|---|---|---|
| Consul UI (catalog, mesh, intentions) | <http://localhost:18500/ui> | none (demo: ACLs off) |
| Vault UI | <https://localhost:18200/ui> | root token in `/demo-state/vault-init.json` (`podman exec demo-vault-setup cat /demo-state/vault-init.json`) |
| Boundary UI | <http://localhost:19200> | printed by the smoke test (`.boundary-admin.json`) |
| demo-api | <http://localhost:18080> | — each request shows a fresh `v-token-…` DB user |

Ports are offset (18xxx/19xxx) so the standalone product stacks in
`../../consul`, `../../vault`, `../../boundary` can run at the same time.

## The money shots

1. `curl http://localhost:18080/` twice — different `db_user_from_vault` each
   time credentials expire; the query travels demo-api → sidecar → **mTLS** →
   sidecar → postgres.
2. `./scripts/smoke-test.sh` — proves the whole chain, including that the
   credentials Boundary brokers are accepted by PostgreSQL.
3. From your workstation (needs `psql` + boundary CLI):

   ```bash
   boundary authenticate password -addr http://localhost:19200 \
     -auth-method-id <ampw_… from smoke test> -login-name admin
   boundary connect postgres -addr http://localhost:19200 \
     -target-id <ttcp_… from smoke test> -dbname appdb
   ```

   You land in a psql shell as a Vault-issued user you never saw a password
   for. `SELECT current_user;` shows it; it stops working 10 minutes later.

4. Intentions: in the Consul UI, flip the `demo-api → postgres-app` intention
   to deny and watch `curl :18080` fail; flip it back.

## Layout

| Path | Purpose |
|---|---|
| `docker-compose.yml` | the whole stack (12 services), reuses the hardened images from `../../{consul,vault,boundary}` |
| `consul/server.json` | single Connect-enabled server + bootstrap intentions (`allow demo-api`, `deny *`) |
| `consul/services.json` | `postgres-app` and `demo-api` registrations with sidecar + upstream definitions |
| `vault/vault-server.hcl` | raft + TLS + Consul service registration |
| `boundary/config.hcl` | controller+worker, keys rendered from `.env` |
| `scripts/vault-setup.sh` | init/unseal, database engine, roles, policies, scoped tokens |
| `scripts/boundary-setup.sh` | scopes, Vault credential store/library, host, target (recovery-KMS auth) |
| `scripts/smoke-test.sh` | full-chain UAT |
| `demo-api/` | app fetching per-request Vault creds, DB via mesh upstream |

## Taking it to a real environment

Everything environment-specific is a substitution point, not a rewrite:

- **Addresses/ports** — container DNS names and the 18xxx/19xxx offsets live
  only in `docker-compose.yml` and `.env` (`BOUNDARY_PUBLIC_ADDR`).
- **Boundary KMS** — swap the three `kms "aead"` blocks for
  awskms/azurekeyvault/gcpckms; working per-cloud examples in
  [`terraform/`](../../terraform), which deploys this same trio on
  AWS/Azure/GCP/VMware.
- **Vault HA + auto-unseal** — add raft `retry_join` + a `seal` stanza (same
  terraform roots show it), replace the 1-share demo init.
- **Consul hardening** — the standalone [`consul/`](../../consul) stack shows
  the production posture (3 servers, TLS RPC, gossip encryption, ACL
  default-deny); enable ACLs here and hand tokens to the sidecars and Vault.
- **Sidecars on a scheduler** — the registrations in `consul/services.json`
  translate 1:1 to Kubernetes/Nomad Connect annotations with Envoy instead of
  the built-in proxy.
- **demo-api** — stands in for any app; the pattern is "read a scoped token,
  ask Vault for creds, talk to your upstream on localhost via the sidecar".
