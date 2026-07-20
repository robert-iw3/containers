# Production deployment — podman Quadlet, one role per VM

`../docker-compose.yml` + `../run_portal.sh` remain the **local test rig**.
This directory is the production path: systemd-managed containers (Quadlet)
spread across dedicated hosts, with per-role kernel/sysctl prep. systemd owns
ordering (`Notify=healthy` gates), restarts, and boot persistence — the
things compose implementations get wrong.

```
role      VM                 runs
----      --                 ----
mesh      consul.internal    Consul server (Connect CA, catalog, intentions)
data      db.internal        Postgres 18 (TLS-only) + pgbackup + consul agent + postgres sidecar
scm       git.internal       Gitea 1.27 (TLS) + consul agent + gitea sidecar
secrets   vault.internal     Vault (raft, TLS, mlock)
identity  sso.internal       Keycloak 26 (OIDC, public)
access    boundary.internal  Boundary controller+worker (the only end-user door)
portal    portal.internal    backstage-a, backstage-b, nginx router, consul agent,
                             egress sidecar (upstreams: postgres :20001, gitea :20002)
```

Mesh traffic (portal→postgres, portal→gitea) rides Connect mTLS between the
host-networked sidecars; intentions stay deny-by-default. Everything else
(Vault, Keycloak, Boundary→postgres) is direct TLS between hosts.

## Order of operations

1. **Prep + PKI.** For each VM: `./deploy.sh <role> <host> --prep` runs
   `host-prep/prep-host.sh` (podman, kernel modules, sysctl profile, file
   limits) — or run it separately. Stage TLS material at
   `/etc/backstage-portal/tls/` on every host first: `ca.crt` everywhere,
   plus the role's cert/key from your PKI:
   - consul: `consul.crt/.key` (SAN: host FQDN) — on mesh, data, scm, portal
   - `postgres.crt/.key` (SANs: `db FQDN`, **`host.containers.internal`**) — owner 70:70, mode 0600
   - `gitea.crt/.key` (SANs: `git FQDN`, **`host.containers.internal`**) — readable by uid 1000
   - `vault.crt/.key`, `keycloak.crt/.key`, `boundary.crt/.key`,
     `portal-proxy.crt/.key` (SAN: each host's FQDN + public name)

   The `host.containers.internal` SANs matter: the portal reaches postgres
   and gitea end-to-end TLS *through* its egress sidecar, addressed by
   podman's host alias.
2. **Images.** Push the four locally built images to your registry:
   `backstage-portal:1.1.0`, `consul:2.0.2`, `vault:2.0.3`,
   `boundary:0.21.3` (mirror the pinned upstream postgres/gitea/nginx/
   keycloak images too if your hosts can't reach public registries).
3. **Deploy in dependency order:**
   ```bash
   cp hosts.env.example hosts.env   # fill in FQDNs, IPs, secrets
   ./deploy.sh mesh     consul.internal   --prep
   ./deploy.sh data     db.internal       --prep
   ./deploy.sh secrets  vault.internal    --prep
   ./deploy.sh identity sso.internal      --prep
   ./deploy.sh scm      git.internal      --prep
   ./deploy.sh access   boundary.internal --prep
   ./deploy.sh portal   portal.internal   --prep
   ```
4. **Provision** (from a bastion/CI job — the compose one-shots translate
   directly; point them at the real endpoints):
   - Vault: init/unseal ceremony, database secrets engine → data host
     (static role `backstage-portal`, dynamic `dba-readonly`), kv-v2,
     policies, portal token → deliver to
     `/etc/backstage-portal/state/backstage-token` on the portal host
     (`../scripts/vault-setup.sh` is the reference implementation).
   - Keycloak: realm `portal`, client `backstage-portal`, users/federation
     (`../scripts/keycloak-setup.sh`), client secret → Vault kv.
   - Gitea: admin, org, seed repos (`../scripts/gitea-setup.sh`).
   - Boundary: scopes, Vault credential store, `dev-portal` target →
     `portal.internal:8443`, `portal-postgres-dba` target → `db.internal:5432`
     (`../scripts/boundary-setup.sh`).
5. **Verify.** Run `../scripts/smoke-test.sh` logic against the real
   endpoints (the assertions are identical; addresses differ).

## Firewall matrix (restrict everything else)

| Host | Port | From |
|---|---|---|
| mesh | 8501, 8502, 8300, 8301/tcp+udp | stack hosts |
| data | 5432 | portal, secrets, identity, access |
| data | 21000 (sidecar) | portal |
| scm | 3000 | admin network; 21001 (sidecar): portal |
| secrets | 8200 | stack hosts + admin |
| identity | 8443 | **public** (browser SSO) |
| access | 9200 (API), 9202 (worker proxy) | **public** (end users) |
| access | 9203 (ops) | monitoring |
| portal | 8443 | **access host only**; 21002 (sidecar): mesh checks |

End users only ever touch `access:9202` (brokered session) and
`identity:8443` (SSO login). The portal itself is reachable solely from the
Boundary worker.

## Host prep (sysctl/kernel) summary

- **common**: ip_forward + bridge netfilter (podman networking), somaxconn/
  syn backlog, inotify + file-max, swappiness 10, nofile 262144.
- **data**: swappiness 1, strict overcommit (`vm.overcommit_memory=2`),
  gentle dirty ratios; optional huge pages note.
- **secrets**: swappiness 0 (disable swap entirely), no core dumps
  (`kernel.core_pattern`, `fs.suid_dumpable=0`); the vault unit adds
  `IPC_LOCK` + `LimitMEMLOCK=infinity` so mlock works.
- **mesh**: UDP gossip buffers, TCP keepalive tuning.
- **access**: conntrack sizing + `tcp_tw_reuse` for many brokered sessions.
- **portal**: larger accept backlogs.

## Notes

- Units are rootful system quadlets (`/etc/containers/systemd`). For
  rootless, move them to `~/.config/containers/systemd`, add
  `loginctl enable-linger`, and raise `net.ipv4.ip_unprivileged_port_start`
  if you lower any port below 1024.
- `backstage-b` orders after `backstage-a` reaches *healthy*
  (`Notify=healthy`), which serializes fresh logical-DB migrations — the
  same first-boot rule the compose rig enforces.
- Scaling beyond one VM per role: mesh → 3 consul servers
  (`bootstrap_expect: 3`), secrets → 3-node raft, data → Postgres HA
  (Patroni et al.), portal → N portal hosts behind the Boundary target's
  host-set.
