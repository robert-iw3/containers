# Troubleshooting toolkit

Every script here was distilled from a real incident hit while hardening
this stack. All are read-only unless the name says otherwise; all honor
`RUNTIME=docker` for Docker hosts.

| Script | Use when | What it does |
|---|---|---|
| `stack-status.sh` | anything looks off | one-screen health of every tier: containers, consul leader/services/intentions, vault seal, boundary ops, portal readiness + routing headers |
| `diagnose-portal.sh [replica]` | a portal replica is unhealthy/503 | classifies the boot log against every known failure signature (missing Vault token/kv secrets, MigrationLocked, DDL race, dead mesh connections, DB auth, TLS trust) and prints the exact fix |
| `fix-migration-locks.sh` | `MigrationLocked` crash loops | stops both replicas, **dedupes** duplicate knex lock rows (which make the lock permanently unacquirable) and unlocks, then boots A→B in order |
| `check-mesh.sh [--repair]` | portal can't reach DB/Gitea; "Connection terminated unexpectedly" | verifies sidecars, agent registrations, upstream listeners, and an end-to-end mesh fetch; `--repair` bounces the sidecars (needed after core containers get recreated) |
| `check-vault-secrets.sh` | `entrypoint: FAIL ...` on boot | checks every portal-state token file and reads each required secret with the portal's *own* scoped token, exactly like the entrypoint does; reports TTL |
| `debug-boundary-session.sh` | end users can't reach the portal | walks auth → target ids → worker `public_addr` → direct target reachability → live session with the connect log captured, and decodes the two classic failures (worker-address hairpin, stale target port) |
| `collect-diagnostics.sh` | escalating / offline analysis | tarball of states, redacted logs + inspects, consul catalog/intentions, vault status, plugin DBs and lock-table contents |
| `install-ca.sh [--system]` | browser won't trust / can't import the demo CA | extracts the CA to a **visible** `~/portal-demo-ca.pem` (Firefox's file picker can't open the hidden `.portal-ca.crt`, and snap Firefox can't read dotfiles at all), installs it into every Firefox NSS profile via `certutil` (Firefox ignores the system store), and with `--system` also into the OS trust store. Manual import must use the **Authorities** tab — the "Your Certificates" tab expects a private key and fails with "you do not own the corresponding private key" |

## Incident → script map (from this stack's actual history)

- Portal crash-loops with `MigrationLocked`, or `create table ... already
  exists` on first boot → `fix-migration-locks.sh` (root causes: replicas
  racing DDL on fresh DBs; crashes stranding locks; duplicate lock rows).
- Portal 503 with DB `Connection terminated unexpectedly` after
  restarting/recreating consul or postgres → `check-mesh.sh --repair`.
- Portal stuck at `entrypoint: waiting for Vault token` or failing kv reads
  → `check-vault-secrets.sh`, then rerun the matching setup one-shot
  (`podman start -a backstage-vault-setup` / `scripts/gitea-setup.sh` /
  `scripts/idp-setup.sh`).
- Boundary session authorizes but the fetch dies (`SSL unexpected eof`) →
  `debug-boundary-session.sh`: either the worker `public_addr` is not
  reachable from where `connect` runs (use the in-network `boundary:9202`),
  or the target's default port is stale (proxy moved 8080→8443 once).
- Browser gets `PR_CONNECT_RESET_ERROR` on 127.0.0.1:27007 while curl works
  → the `boundary connect` proxy corrupts websocket frames under PARALLEL
  connections ("unexpected rsv bits" in the worker log — upstream
  coder/websocket concurrent-reader bug) and dies; browsers open ~6
  connections at once. Mitigated two ways: nginx serves **HTTP/2** so
  browsers multiplex over a single connection, and `portal-session.sh` runs
  the listener under a respawn loop so a crash self-heals in 2s.
- Boundary auth suddenly failing after a rebuild → stale
  `.boundary-admin.json` from a previous boundary DB; the smoke test now
  auto-refreshes, `debug-boundary-session.sh` warns explicitly.

## Scripting rules learned the hard way (apply to any new script here)

- Never `podman logs | grep -q PAT` under `set -o pipefail` — grep's early
  exit SIGPIPEs podman and a *match* reads as failure. Use
  `[ "$(... | grep -c PAT)" -gt 0 ]`.
- Never `| head -1` inside `$( )` under pipefail — use `| sed -n 1p`.
- `pkill -f "some string"` matches its own `sh -c` wrapper — bracket a
  character: `pkill -f "some str[i]ng"`.
- Reading the `portal-state`/`portal-certs` volumes needs `--user root`
  under rootless podman (files are owned by container-root = your host uid).
