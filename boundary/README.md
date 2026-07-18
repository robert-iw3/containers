## Hashicorp Boundary

<p align="center">
  <img src="https://www.hashicorp.com/_next/image?url=https%3A%2F%2Fwww.datocms-assets.com%2F2885%2F1714171044-blog-library-product-boundary-dark-gradient.jpg&w=3840&q=75" />
</p>

AWS Example:
<p align="center">
  <img src="https://raw.githubusercontent.com/hashicorp/boundary-reference-architecture/main/arch.png" />
</p>

Hardened Boundary **0.21.3** image (GPG-verified release binary on Alpine,
non-root user) running a combined controller + worker backed by PostgreSQL 17.

No key material is baked into the image: the three AEAD KMS keys (root,
worker-auth, recovery) and the database credentials come from `.env` and are
rendered into the config at container start.

For Boundary brokering **Vault-issued credentials** to targets over a Consul
mesh, see [`integration-demos/hashicorp-stack`](../integration-demos/hashicorp-stack).

## Quick start (UAT / smoke)

```bash
./scripts/bootstrap-env.sh       # writes .env with random keys (chmod 600)
podman-compose up -d --build     # docker compose works too
./scripts/smoke-test.sh
```

First start runs `boundary database init` (idempotent) and then the server in
the same container; the generated admin credentials are printed once in the
`boundary-main` logs. The smoke test captures them into
`boundary/.boundary-admin.json` (`chmod 600`, gitignored), authenticates, and
lists the generated scopes/targets.

- Admin UI / API: <http://localhost:9200>
- Worker proxy: `localhost:9202` — health/metrics: `localhost:9203`
- Postgres is **not** published to the host.

## Layout

| Path | Purpose |
|---|---|
| `Dockerfile` | multi-stage build, GPG + SHA256 verified binary |
| `config.hcl` | controller+worker config; `__PLACEHOLDERS__` rendered from `.env` at start |
| `docker-compose.yml` | postgres + boundary (init-then-serve) |
| `scripts/bootstrap-env.sh` | generate `.env` (random postgres password + AEAD keys) |
| `scripts/smoke-test.sh` | health/auth/scope UAT |
| `configuration/`, `deploy_boundary.yml`, `boundary-kubernetes.yml` | Ansible and Kubernetes extras |

## Configuring for other environments

- **Client-facing address**: set `BOUNDARY_PUBLIC_HOST` in `.env` to the
  address clients use to reach the worker proxy (9202).
- **Production KMS**: replace the `kms "aead"` blocks in `config.hcl` with
  awskms / azurekeyvault / gcpckms / transit — working cloud examples with
  per-purpose KMS keys in [`terraform/`](../terraform).
- **TLS**: the API listener is plaintext here for UAT; in production either
  terminate TLS at a load balancer or set `tls_cert_file`/`tls_key_file` on
  the `api` listener.
- **Separate workers**: give workers their own config (worker block +
  `worker-auth` KMS only) and point `initial_upstreams` at the controllers'
  cluster address (9201) — see the Terraform roots for the split layout.

## Cleanup

```bash
podman-compose down -v        # -v wipes the database (admin creds regenerate)
rm -f .boundary-admin.json
```
