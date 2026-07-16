# Troubleshooting

| Script | What it checks | Fixes? |
|---|---|---|
| [`stack-health.sh`](stack-health.sh) | Every container's status/health; tails errors from any that aren't healthy | no |
| [`podman-socket.sh`](podman-socket.sh) | The rootless podman API socket Traefik needs (dead unit, or the "socket path became a directory" footgun) | `--repair` |
| [`socket-proxy-check.sh`](socket-proxy-check.sh) | Socket proxy is healthy and correctly **allows discovery / denies writes**; Traefik provider connectivity | no |
| [`oidc-verify.sh`](oidc-verify.sh) | Full Authelia OIDC chain: discovery, JWKS, authorize accept/reject, token-endpoint client auth, dashboard forward-auth, optional live login | no |
| [`nextcloud-checks.sh`](nextcloud-checks.sh) | `occ` status, background-job mode, missing indices, registered OIDC providers, and the **OIDC back-channel reachability** from the app container | no |

## Usage

```sh
cd nextcloud/troubleshooting
./stack-health.sh
./socket-proxy-check.sh
./oidc-verify.sh
./nextcloud-checks.sh
```

Against a production deployment these need nothing extra — real DNS and a valid
ACME cert. For a local / self-signed environment, export the curl knobs first:

```sh
export CURL_INSECURE=1                     # or CACERT=/path/to/ca.crt
export RESOLVE="auth.example.test:8443:127.0.0.1 nextcloud.example.test:8443:127.0.0.1"
./oidc-verify.sh
```

Optional live first-factor login test (skipped unless set):

```sh
AUTH_TEST_USER=ncadmin AUTH_TEST_PASS='...' ./oidc-verify.sh
```

## When the socket dies

Symptom: Traefik logs `Cannot connect to the Docker daemon`, every route 404s.

```sh
./podman-socket.sh            # diagnose
./podman-socket.sh --repair   # remove stale dir + restart podman.socket
docker restart nextcloud-socket-proxy nextcloud-traefik
```

## Reuse for ownCloud

The generic scripts (`stack-health.sh`, `podman-socket.sh`,
`socket-proxy-check.sh`) derive the container/network prefix from the parent
directory name — copy this folder to `owncloud/troubleshooting/` and they target
the `owncloud-*` stack. `oidc-verify.sh` and `nextcloud-checks.sh` are
Nextcloud-specific.
