# Troubleshooting scripts

Operational diagnostics for the ownCloud stack. All read config from `../.env`
(never shell-sourced, so `$`-containing hashes are safe) and auto-detect
`docker` vs `podman`. Most are read-only; only `podman-socket.sh --repair`
changes anything.

The first three are the same self-deriving scripts shipped with the Nextcloud
stack — they target `owncloud-*` containers and the `owncloud_socket` network
purely from this folder's parent directory name.

| Script | What it checks | Fixes? |
|---|---|---|
| [`stack-health.sh`](stack-health.sh) | Every container's status/health; tails errors from any that aren't healthy | no |
| [`podman-socket.sh`](podman-socket.sh) | The rootless podman API socket Traefik needs (dead unit, or the "socket path became a directory" footgun) | `--repair` |
| [`socket-proxy-check.sh`](socket-proxy-check.sh) | Socket proxy is healthy and correctly **allows discovery / denies writes**; Traefik provider connectivity | no |
| [`owncloud-checks.sh`](owncloud-checks.sh) | `occ` status, background-job mode, Redis/cache wiring, trusted domains/overwrite settings, image healthcheck | no |
| [`oidc-verify.sh`](oidc-verify.sh) | Authelia OIDC chain (discovery, JWKS, authorize accept/reject, token-endpoint client auth, dashboard forward-auth) — only with the `sso` profile | no |

`oidc-verify.sh` only applies when the optional `sso` profile (Authelia) is
running; otherwise it reports the portal as unreachable.

## Usage

```sh
cd owncloud/troubleshooting
./stack-health.sh
./socket-proxy-check.sh
./owncloud-checks.sh
```

For a local / self-signed environment, export the curl knobs first:

```sh
export CURL_INSECURE=1                     # or CACERT=/path/to/ca.crt
export RESOLVE="owncloud.example.test:8443:127.0.0.1"
```

## When the socket dies

Symptom: Traefik logs `Cannot connect to the Docker daemon`, every route 404s.

```sh
./podman-socket.sh --repair
docker restart owncloud-socket-proxy owncloud-traefik
```

## Status note

`owncloud-checks.sh` targets ownCloud 10 `occ` but has not yet been run against
a live instance — the ownCloud stack has only had static validation so far. It
degrades gracefully (each `occ` call tolerates failure); adjust command names if
your ownCloud version differs.
