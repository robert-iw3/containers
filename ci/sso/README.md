# Devops stack SSO pattern

`artifactory`, `bitbucket`, `confluence`, `gitea`, `grafana`, `hyperdx`,
`saltstack` and `sonarqube` share one deployment shape:

```
browser ──TLS──▶ traefik ──forwardAuth──▶ tinyauth ──▶ identity provider
                    │                                  (local users or OIDC)
                    └──▶ application  (internal network, no host port)
```

Each stack directory holds:

| Path | Purpose |
| --- | --- |
| `sso/docker-compose.yml` | the deployable stack — traefik, tinyauth, the application and its datastore |
| `sso/.env.example` | every setting, with placeholders |
| `sso/traefik-dynamic.yml` | TLS store, security headers, forwardAuth middleware |
| `uat/run-uat.sh` | stands the stack up over TLS and asserts build → login |
| `ansible/deploy.yml` | deploys that same compose file |

The UAT runs the *same* compose file ansible deploys, with a generated
`uat/.env`; nothing is validated that is not also shipped.

## Authentication

tinyauth is the policy enforcement point. It verifies credentials against
local bcrypt users by default, or against any OIDC provider through its
`GENERIC_*` settings — see [`tinyauth-oidc.env.example`](tinyauth-oidc.env.example)
for the endpoints of the `zitadel`, `authentik` and `keycloak` stacks in
this repository. Switching providers is an `.env` change; no stack is
rebuilt.

### Identity passthrough

traefik copies tinyauth's `Remote-User`, `Remote-Name`, `Remote-Email` and
`Remote-Groups` response headers onto the upstream request. Applications
that can trust a pre-authenticated header sign the user in directly, so a
session costs one login rather than two:

| Stack | Mechanism |
| --- | --- |
| grafana | `auth.proxy` (`GF_AUTH_PROXY_*`) |
| gitea | reverse proxy authentication (`GITEA__service__*`) |
| sonarqube | HTTP header SSO (`SONAR_WEB_SSO_*`) |

The rest keep their own login and are gated at the proxy only: Artifactory
OSS has no HTTP SSO, Bitbucket and Confluence need a licensed SSO app, and
HyperDX and SaltStack authenticate their own API clients.

Trusting a header is only safe while the header cannot be forged, which
this pattern enforces two ways: the application publishes no host port and
is reachable solely through traefik, and traefik overwrites the `Remote-*`
headers on every request from the forwardAuth response. Each `run-uat.sh`
asserts the second property by replaying a spoofed header.

### Machine traffic

Git clients, scanners, registry clients and agents cannot complete an
interactive login, so their paths route to the application without the
forwardAuth middleware and authenticate with the application's own tokens.
Those bypass routers are declared per stack in `sso/docker-compose.yml`
and are the narrowest path match that works — e.g. gitea exposes
`/api/v1` and the git transport endpoints, not all of `/`.

## Running

```sh
cd <stack>/uat && ./run-uat.sh          # bring up, assert, leave running
cd <stack>/uat && ./run-uat.sh --down   # tear down
```

Run one stack at a time; the images are large and several want 2–4 GB of
heap. Host ports are unique per stack so a previous run does not have to be
torn down first.

Deployment uses the same compose file:

```sh
cd <stack>/ansible && ansible-playbook -i inventory.ini deploy.yml
```

Lint the playbooks with `ci/ansible-lint.sh` (containerised; no host
ansible needed).
