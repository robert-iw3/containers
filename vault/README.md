## Hashicorp Vault

<p align="left">
    <a href="https://github.com/robert-iw3/apps/actions/workflows/vault-ghcr.yml" alt="Docker CI">
          <img src="https://github.com/robert-iw3/apps/actions/workflows/vault-ghcr.yml/badge.svg" /></a>
</p>

<p align="center">
  <img src="https://www.datocms-assets.com/2885/1620082983-blog-library-product-vault-dark-graphics.jpg" />
</p>

Hardened Vault **2.0.3** image (GPG-verified release binary on Alpine, non-root
user) with a production-shaped standalone deployment: integrated raft storage,
TLS listener from a locally generated CA, JSON logging, UI enabled.

For Vault wired into Consul + Boundary end to end, see
[`integration-demos/hashicorp-stack`](../integration-demos/hashicorp-stack).

## Quick start (UAT / smoke)

```bash
podman-compose up -d --build     # docker compose works too
./scripts/smoke-test.sh
```

The smoke test:
1. waits for the API over TLS,
2. initializes with 1 key share / threshold 1 (**UAT only**) — unseal key and
   root token land in `vault/.vault-init.json` (`chmod 600`, gitignored),
3. unseals, enables `kv-v2`, does a write/read round-trip, enables file audit.

UI: <https://localhost:8200/ui> (self-signed cert — accept the warning; the CA
lives in the `vault-certs` volume as `vault-ca.crt.pem`).

## Layout

| Path | Purpose |
|---|---|
| `Dockerfile` | multi-stage build, GPG + SHA256 verified binary |
| `config/vault-server.hcl` | raft + TLS server config (the main deploy knob) |
| `config/generate_certs.py` | idempotent CA/server cert generation (runs in the `vault-certs-init` container) |
| `docker-compose.yml` | cert init + server |
| `scripts/smoke-test.sh` | init/unseal/KV UAT |
| `agent/`, `api/`, `baremetal/`, `deploy_vault.yml` | Vault agent example, API gateway, Vagrant, Ansible extras |

## Configuring for other environments

- **Addresses / SANs**: set `VAULT_TLS_EXTRA_SANS` (e.g.
  `DNS:vault.example.com,IP:10.0.0.5`) on `vault-certs-init`, and adjust
  `api_addr` / `cluster_addr` in `config/vault-server.hcl`.
- **Real certificates**: drop them into the `vault-certs` volume (or bind-mount
  a directory over `/certs`) and remove the init container.
- **Production seal**: replace Shamir with a `seal` stanza (awskms /
  azurekeyvault / gcpckms) — working cloud examples with KMS auto-unseal live
  in [`terraform/`](../terraform).
- **Clustering**: add raft `retry_join` blocks (static addresses or cloud
  auto-join) — per-cloud configs in `terraform/`.
- `disable_mlock = true` follows HashiCorp's recommendation for integrated
  storage (disable swap on the host instead); it also lets the container keep
  `no-new-privileges`.

## Cleanup

```bash
podman-compose down -v        # -v wipes raft data and certs
rm -f .vault-init.json
```
