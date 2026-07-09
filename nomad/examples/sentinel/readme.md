# Sentinel policies (Nomad Enterprise only)

Sentinel admission control requires Nomad Enterprise; OSS clusters cannot load
these. Apply with:

```bash
nomad sentinel apply -level=soft-mandatory <name> <file>.sentinel
```

| Policy | Purpose |
|---|---|
| `allowed-drivers.sentinel` | Only podman (and optionally docker) task drivers may be used |
| `no-latest-tag.sentinel` | Container images must be pinned, no `:latest` |
| `require-resources.sentinel` | Every task must declare CPU and memory limits |

On OSS, the closest equivalents are ACL policies (limiting who can submit jobs)
and job validation in the deployment pipeline before submission.
