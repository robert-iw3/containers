# Deployment pipeline into Nomad

One connector, three avenues to invoke it. Any container directory in this repo
(or anywhere) gets built, pushed to a registry the cluster can pull from, and
initialized as a running Nomad workload — with the deploy step blocking until
the deployment is actually healthy (and auto-reverting on failure via the
job's `update` stanza).

```
             ┌──────────────────┐
  GitHub CI ─┤                  │
  GitLab CI ─┤ pipeline/ship.py ├──► registry (GHCR) ──► Nomad API :4646
  local dev ─┤ build/push/deploy│         ▲                  │
             └──────────────────┘   clients pull image   deployment health
```

## The connector

`ship.py` is stdlib-only Python — no pip installs in CI, no external tools
besides podman (docker fallback) for the build/push steps. The deploy step is
pure HTTP against the Nomad API.

```bash
export NOMAD_ADDR=https://<server-or-lb>:4646
export NOMAD_TOKEN=<acl token>
export NOMAD_CACERT=ca.pem

# any directory with a Dockerfile — e.g. one of this repo's containers
python3 pipeline/ship.py build ../keycloak --image ghcr.io/org/keycloak:$(git rev-parse --short HEAD)
python3 pipeline/ship.py push  --image ghcr.io/org/keycloak:abc1234
python3 pipeline/ship.py deploy --image ghcr.io/org/keycloak:abc1234 --name keycloak --port 8080 --count 2
```

`deploy` parses a generated (or custom `--job`) jobspec through
`/v1/jobs/parse`, dry-runs it with `/v1/job/:id/plan`, registers it, then polls
`/v1/job/:id/deployment` until `successful` — a failed health check surfaces as
a non-zero exit in CI, and Nomad auto-reverts to the previous version.

Custom jobspecs: pass `--job path/to/app.nomad.hcl` containing the literal
placeholder `__IMAGE__` where the image reference goes; everything else in the
file is yours (volumes, Consul Connect, constraints, ...).

## CI avenues

- `github-workflow.yml.example` — build+push to GHCR with the ambient
  `GITHUB_TOKEN`, deploy with `NOMAD_*` repository secrets.
- `gitlab-ci.yml.example` — same flow with GitLab CI/CD variables.

Both trigger per-directory on path changes, mirroring this repo's existing
per-container build matrix.

## Access token

Don't use the bootstrap management token in CI. Mint a deploy-scoped token:

```bash
nomad acl policy apply deploy - <<'EOF'
namespace "default" {
  policy       = "write"
  capabilities = ["submit-job", "dispatch-job", "read-job", "read-logs"]
}
EOF
nomad acl token create -name=ci-deploy -policy=deploy
```

Network path: the CI runner needs to reach `:4646`, so its egress IP/CIDR must
be in `admin_cidr_blocks` (terraform avenue) / `nomad_allowed_ips` (ansible
avenue), or the runner must sit inside the VPC/VPN.
