# Terraform — HashiCorp stack on AWS / Azure / GCP / VMware

Full-stack deployments of **Consul 2.0.2 + Vault 2.0.3 + Boundary 0.21.3**,
one root per platform, sharing two modules:

| Path | Purpose |
|---|---|
| `modules/hashicorp-install` | cloud-agnostic cloud-init: GPG/SHA-verified binary install, config render (`__PRIVATE_IP__`/`__HOSTNAME__` substituted at boot), systemd unit |
| `modules/internal-ca` | throwaway internal CA + leaf certs for Consul RPC and Vault raft/API TLS |
| `aws/` | VPC, auto-join by EC2 tags, **KMS auto-unseal**, per-purpose Boundary KMS keys, RDS PostgreSQL 17 |
| `azure/` | VNet + NSG, auto-join by VM tags via managed identity, **Key Vault auto-unseal**, PostgreSQL Flexible Server (private) |
| `gcp/` | VPC, auto-join by network tags, **Cloud KMS auto-unseal**, Cloud SQL PostgreSQL 17 (private IP) |
| `vmware/` | vSphere clones with static IPs via guestinfo cloud-init, Postgres VM, Shamir seal (transit noted) |

Every root deploys: 3 Consul servers (TLS RPC, gossip encryption, ACL
default-deny, Connect enabled), 3 Vault servers (raft + retry_join/auto-join,
TLS, auto-unseal where a KMS exists), 1 Boundary controller (database
auto-init; admin credentials land in `/var/log/boundary-db-init.log`) and N
workers.

## Containerized CLI (build + syntax validation)

All terraform work runs through the `localhost/terraform:1.15.8` image built
from [`Dockerfile`](Dockerfile) (alpine 3.24, GPG + SHA256-verified CLI) — no
host terraform install needed.

```bash
# validate every root (fmt -check + init + validate), builds image on demand
./scripts/validate.sh            # or: ./scripts/validate.sh aws

# drive a real deployment, e.g. AWS
cd aws && cp terraform.tfvars.example terraform.tfvars   # then edit
podman run --rm -it \
  -v "$PWD/..":/workspace:z -w /workspace/aws \
  -v tf-plugin-cache:/tfcache \
  -v "$HOME/.aws":/root/.aws:ro,z \
  localhost/terraform:1.15.8 init

podman run --rm -it \
  -v "$PWD/..":/workspace:z -w /workspace/aws \
  -v tf-plugin-cache:/tfcache \
  -v "$HOME/.aws":/root/.aws:ro,z \
  localhost/terraform:1.15.8 apply
```

Azure: `-e ARM_*` env vars or a mounted `az` profile. GCP:
`-v "$HOME/.config/gcloud":/root/.config/gcloud:ro,z` or
`-e GOOGLE_APPLICATION_CREDENTIALS`. VMware: `-e VSPHERE_SERVER -e VSPHERE_USER -e VSPHERE_PASSWORD`.

## After apply

1. `terraform output` prints the entry points (Consul UI, Vault addr,
   Boundary addr) and CA certs.
2. Vault: auto-unseals via KMS on AWS/Azure/GCP — run
   `vault operator init` once against node 0 (recovery keys instead of unseal
   keys). On VMware, init + unseal manually (Shamir).
3. Consul: `consul acl bootstrap` on any server.
4. Boundary: admin credentials are in `/var/log/boundary-db-init.log` on the
   controller.

## Production notes

- `allowed_admin_cidrs = []` (default) exposes nothing to the internet; set it
  to your operator addresses only. For real deployments move the stack to
  private subnets behind a bastion/LB — the SG/NSG/firewall rules are already
  separated into "internal" and "admin" to make that split easy.
- The internal CA, the Consul gossip key, DB passwords, and (VMware only)
  Boundary AEAD keys live in terraform state — use an encrypted remote
  backend, or swap in your PKI and a `transit` seal.
- Versions are pinned via `consul_version` / `vault_version` /
  `boundary_version` variables, matching the container images in this repo.
