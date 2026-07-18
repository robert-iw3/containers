
<p align="center">
  <img src="https://repository-images.githubusercontent.com/14125254/27f3ac80-6a20-11ea-8e4a-7151721107d3" />
</p>

# HashiCorp Consul

Hardened Consul **2.0.2** image (GPG-verified release binary on Alpine,
ClamAV-scanned at build, non-root user) and a production-shaped 3-server
cluster: TLS on server RPC (`verify_server_hostname`), gossip encryption,
ACLs in default-deny, HTTPS API + UI.

No key material is baked into the image — the CA, server certificate, and
gossip key are generated once at first start by the `consul-init` container
and live in named volumes, so every deployment gets unique keys.

For Consul as a Connect service mesh fronting real workloads, see
[`integration-demos/hashicorp-stack`](../integration-demos/hashicorp-stack).

## Quick start (UAT / smoke)

```bash
podman-compose up -d --build     # docker compose works too
./scripts/smoke-test.sh
```

The smoke test waits for a raft leader, bootstraps the ACL system (management
token lands in `consul/.consul-bootstrap.json`, `chmod 600`, gitignored), then
verifies: 3 alive members, raft peers, KV round-trip, service registration.

UI: <https://localhost:8501/ui> — log in with the token printed by the smoke
test. DNS: port 8600 (tcp/udp).

## Layout

| Path | Purpose |
|---|---|
| `Dockerfile` | multi-stage build, GPG + SHA256 verified binary, ClamAV scan |
| `config/server.json` | shared server config (node identity comes from each container's hostname) |
| `docker-compose.yml` | init (certs + gossip key) + 3 servers |
| `scripts/smoke-test.sh` | leader/ACL/KV/catalog UAT |
| `consul-agent.json` | client agent example (auto_encrypt) |
| `vault-storage.json` | ACL policy for Vault's Consul storage/registration |
| `baremetal/`, `deploy_consul.yml` | Vagrant and Ansible extras |

## Configuring for other environments

- **Cluster size / naming**: `bootstrap_expect` and `retry_join` in
  `config/server.json`; add server services in the compose file. In clouds use
  auto-join, e.g. `retry_join = ["provider=aws tag_key=... tag_value=..."]` —
  working examples in [`terraform/`](../terraform).
- **Client agents**: start from `consul-agent.json`; clients get TLS via
  `auto_encrypt` and need only the CA plus the gossip key.
- **Exposed surface**: only 8501 (HTTPS API/UI) and 8600 (DNS) are published;
  plaintext 8500 stays on the container loopback for healthchecks.
- **ACL tokens**: after bootstrap, mint scoped policies/tokens instead of using
  the management token day-to-day.

## Cleanup

```bash
podman-compose down -v        # -v wipes data, certs, and the gossip key
rm -f .consul-bootstrap.json
```
