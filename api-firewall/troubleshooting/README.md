# Troubleshooting scripts

Operational diagnostics for the API Firewall stacks (main, demo, UAT and
integrations). All read config from `../.env` (never shell-sourced) and
auto-detect `docker` vs `podman`. Everything here is **read-only** — the
scripts diagnose, they never change state.

| Script | What it checks | Typical symptom it pinpoints |
|---|---|---|
| [`stack-health.sh`](stack-health.sh) | Status/health of every `api-firewall*`/`apifw-*` container; tails errors from unhealthy ones | "something is down but I don't know what" |
| [`spec-check.sh`](spec-check.sh) | OpenAPI spec validity **before** mounting: JSON, 3.0-vs-3.1, numeric `exclusiveMinimum` (modern FastAPI output), empty paths, missing securitySchemes | firewall crash-loops with `cannot unmarshal number into field Schema.exclusiveMinimum` |
| [`firewall-probe.sh`](firewall-probe.sh) | Effective `APIFW_*` config, liveness/readiness, live block behaviour on the edge (unknown path → block code, scanner UA → CRS 403) | "is it actually blocking?", "which layer is on?" |
| [`backend-check.sh`](backend-check.sh) | DNS + HTTP reachability of `APIFW_SERVER_URL` from **inside** the firewall container | `failed to resolve host`, readiness probe failing |

## Usage

```sh
cd api-firewall/troubleshooting
./stack-health.sh
./spec-check.sh                 # or: ./spec-check.sh ../uat/openapi.json
./firewall-probe.sh
./backend-check.sh
```

Target a different stack (e.g. the UAT one) with environment overrides:

```sh
FIREWALL_CONTAINER=apifw-uat-firewall EDGE_URL=http://127.0.0.1:8081 ./firewall-probe.sh
FIREWALL_CONTAINER=apifw-uat-firewall ./backend-check.sh
```

TLS deployments: pass `CACERT=../certs/ca.crt.pem` (or `CURL_INSECURE=1` for
throwaway environments) so the edge probes can complete, and use
`EDGE_URL=https://...`.

## Diagnosis order

1. `stack-health.sh` — is everything running/healthy?
2. Container crash-looping → `spec-check.sh` (parser errors) and
   `backend-check.sh` (DNS/connectivity at startup).
3. Running but traffic misbehaving → `firewall-probe.sh`: readiness tells you
   whether the backend link is broken; the block probes tell you whether
   validation/WAF are actually enforcing; effective-config shows what the
   container really loaded (not what you think `.env` says).
