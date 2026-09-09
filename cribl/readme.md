# Cribl Stream

A leader, N workers, and two components built on them: an integration lab that
measures the volume reduction a pipeline achieves and the control coverage it
retains, and a set of templates for standing up a new Cribl-to-Splunk
integration.

## Layout

| Path | What it is |
| --- | --- |
| `docker-compose.yml` | the leader/worker stack |
| `leader-config/` | the leader's own config; Cribl writes `auth/`, `groups.yml` here |
| `group-default/` | config for the `default` worker group |
| `integration-lab/` | 15 log sources through Cribl into Splunk, with the A/B comparison that measures the reduction |
| `templates/` | render a deployable worker group for a new Cribl-to-Splunk integration |
| `docs/` | the implementation guide, the measured results, and the topology diagram |
| `demo/` | a single-node demo that generates logs and processes them end to end |
| `custom-pipelines/` | per-format pipeline deployment (csv, json, xml, ms-sql) |
| `uat.sh` | acceptance test for the stack |
| `deploy_cribl.py`, `cribl-k8s.yaml` | Ansible and Kubernetes paths |

Pinned to Cribl **4.19.2** (build `89cac507`). `ci/cribl-release-check.sh`
verifies that the tarball and image tag resolve and that every version
reference under `cribl/` matches the pin.

## Where to start

**Standing up a new integration.** `templates/` renders a complete worker group
— Sources, Destinations, routes and one pipeline per source family — from a
single `site.env`. Every setting outside that file is site-independent, because
the record formats these pipelines parse are set by the vendor, not your site.

```bash
cd templates
cp site.env.example site.env      # edit the destination, indexes and rates
./render.sh out/
./validate.sh out/                # checks against Cribl's own shipped schema
```

**Measuring the reduction before deployment.** `integration-lab/` runs the
whole path end to end and measures the result: every record goes through Cribl into one
index and straight to Splunk into another, so the "no pipeline" baseline is
measured rather than assumed.

```bash
cd integration-lab
./run-lab.sh
```

Results and method are in [docs/cribl-value-measured.md](docs/cribl-value-measured.md).
The ports and protocols of the whole path are in
[docs/topology/components-ports.svg](docs/topology/components-ports.svg).

## Configuration is files, not environment variables

Cribl reads Sources and Destinations from files under `$CRIBL_HOME`. It has no
`CRIBL_SPLUNK`, `CRIBL_ELASTIC`, `CRIBL_HEC`, `CRIBL_SYSLOG`, `CRIBL_KAFKA`,
`CRIBL_STATSD` or `CRIBL_TCPJSON` variable — none of those appears in Cribl's
environment-variable documentation. Setting them configures nothing while the
stack still boots, passes its healthcheck, and publishes ports that nothing
listens on.

Two config paths, and they are not interchangeable:

| What | Where |
| --- | --- |
| The leader's own config | `/opt/cribl/local/cribl` → `./leader-config` |
| A worker group's config | `/opt/cribl/groups/<group>/local/cribl` → `./group-default` |

Files placed at `local/cribl/groups/<group>/` are silently ignored.

`CRIBL_VOLUME_DIR` is deliberately not set. It relocates `CRIBL_HOME`, so
setting it to the same path a config volume is mounted at produces a doubled
`local/local/cribl` and orphans the state volume.

## Running

```bash
cp .env.example .env      # set CRIBL_DIST_TOKEN
podman compose up -d
podman compose up -d --scale workers=3
```

`CRIBL_DIST_TOKEN` has no default. It authenticates the channel that carries
the entire config bundle, including every Destination credential. Cribl's
default token, `criblmaster`, is documented and therefore not a secret.

The UI is on <http://127.0.0.1:19000>, loopback-bound because first-boot
credentials are `admin/admin`. Workers publish no host ports: a fixed host
port prevents a second worker from starting.

## Changing group config

Editing `group-default/` is not enough. The leader must commit and deploy for
workers to receive it:

```bash
TOK=$(curl -s -X POST http://127.0.0.1:19000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}' | jq -r .token)

C=$(curl -s -X POST -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"message":"seed","group":"default"}' \
  http://127.0.0.1:19000/api/v1/version/commit | jq -r .items[0].commit)

curl -s -X PATCH -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d "{\"version\":\"$C\"}" \
  http://127.0.0.1:19000/api/v1/master/groups/default/deploy
```

## Never mount a volume on a worker's /opt/cribl/state

A worker applies a config bundle by renaming
`state/distributed/bundles/<id>/local/cribl` over `/opt/cribl/local/cribl`. A
volume makes those two different filesystems, `rename(2)` fails with `EXDEV`,
and both the apply and the revert fail. The worker then holds a stale
config-update lock and accepts no further configuration, while its healthcheck
still passes and the leader still lists it as healthy. Worker
state is disposable; the config comes from the leader.

## Tests

```bash
./uat.sh          # the leader/worker stack
cd demo && ./smoke-test.sh
```

`uat.sh` asserts what the container healthcheck does not: that both workers registered, that
the seeded group config loaded rather than merely existing on disk, that
bundles apply without EXDEV, and that an event traverses a worker.

**One assertion currently fails**, deliberately: the worker binds no listener
for the syslog Source even though that Source is present and enabled in the
worker's own applied config. Config distribution is proved; Source activation
is not. The check is left failing rather than removed, to record that a container
passing its healthcheck is not necessarily processing events.

`demo/smoke-test.sh` proves its own assertion helpers before using them.
Its previous `printf | grep -q` form inverted under `set -o pipefail`. On a
payload larger than the 64 KiB pipe buffer, `grep -q` exits on the first match,
`printf` dies with SIGPIPE, and the pipeline reports exit status 141. A
`! ... grep -q` safety check therefore reports PASS for the violation it guards
against. Both PII-redaction assertions had that defect.

## Secrets

`.env`, `certs/`, `**/auth/` and `custom-pipelines/*/config/config.ini` are
gitignored; only `config.ini.example` is tracked. Anything Cribl generates
(`cribl.secret`, `users.json`, keys) stays out of the repository.
