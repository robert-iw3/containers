<p><a target="_blank" href="https://app.eraser.io/workspace/VT8kbHJC0QzMNWhI9DJx" id="edit-in-eraser-github-link"><img alt="Edit in Eraser" src="https://firebasestorage.googleapis.com/v0/b/second-petal-295822.appspot.com/o/images%2Fgithub%2FOpen%20in%20Eraser.svg?alt=media&amp;token=968381c8-a7e7-472a-8ed6-4a6626da5501"></a></p>

# Sonarqube
![diagram-export-11-17-2023-9_29_11-AM.png](/.eraser/VT8kbHJC0QzMNWhI9DJx___LwMfdHxN5TbOs3GbthKdogHwLmz1___Is7YxdU7vmt1IkURH2JBJ.png "diagram-export-11-17-2023-9_29_11-AM.png")

## SonarQube + Keycloak full stack

[`sonarqube/stack/`](sonarqube/stack/) is a complete, config-driven code-quality
environment with real single sign-on, wired end to end:

```
browser ─TLS→ traefik ─┬─ forwardAuth → tinyauth ──OIDC──→ keycloak ── keycloak-db
                       ├──→ sonarqube (header SSO) ───────── sonar-db
                       └──→ keycloak (login UI)
 backups ── pg_dump → both databases
```

- **Real OIDC SSO** — tinyauth is a Keycloak relying party; users log in at
  Keycloak and SonarQube signs them in from the forwarded identity (one login,
  no local password). The apps carry no host port; traefik is the only route.
- **One source of truth** — [`stack.yaml`](sonarqube/stack/stack.yaml) drives
  everything: `scripts/render.sh` generates the env, OIDC client and Keycloak
  realm; `scripts/scan.sh` scans multiple codebases (recursively) with a token;
  the Ansible playbooks read it as vars.
- **Tuned + secured PostgreSQL** per app (performance, autovacuum/WAL for
  longevity, SCRAM-SHA-256, network-scoped `pg_hba`) with a `pg_dump` sidecar.
- **Two deployment modes** — single-host `docker-compose.yml`, or one service
  per VM via Ansible using Podman **Quadlet** systemd units (compose when the
  runtime is Docker).
- **Validated** — `uat/run-uat.sh` stands the whole stack up over TLS and
  asserts build → Keycloak login → SonarQube session, plus header-spoof
  rejection.

The same traefik + tinyauth SSO pattern (local users or any OIDC provider)
fronts the other devops stacks — see [`ci/sso/README.md`](ci/sso/README.md).

## SSO deployment (`sso/`)

`sso/docker-compose.yml` runs SonarQube behind traefik TLS with tinyauth
single sign-on. Interactive traffic is gated by tinyauth, and traefik hands
the authenticated identity to SonarQube's HTTP header SSO (`Remote-User`) so
the browser session signs in. Scanner and CI calls that present an
`Authorization` token bypass the interactive gate — with identity headers
stripped so the token is the only credential SonarQube honours.

tinyauth verifies local users by default, or any OIDC provider via
`sso/tinyauth.env` (see
[`../ci/sso/tinyauth-oidc.env.example`](../ci/sso/tinyauth-oidc.env.example)).

```sh
cd uat && ./run-uat.sh          # TLS + SSO smoke test, build -> login
cd uat && ./run-uat.sh --down   # tear down
cd ansible && ansible-playbook -i inventory.ini deploy.yml   # deploy
```

The shared pattern is documented in [`../ci/sso/README.md`](../ci/sso/README.md).

[﻿What is Sonarqube?](https://docs.sonarqube.org/latest/)

[﻿What is Podman?](https://www.redhat.com/en/topics/containers/what-is-podman)

[﻿Installing Podman](https://podman.io/getting-started/installation)

[﻿rob-weber.gitbook.io/sonarqube/](https://rob-weber.gitbook.io/sonarqube/)


<!--- Eraser file: https://app.eraser.io/workspace/VT8kbHJC0QzMNWhI9DJx --->