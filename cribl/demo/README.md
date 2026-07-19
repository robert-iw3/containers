# Cribl Stream log demo

Self-contained, config-as-files demo of a working log pipeline —
something to build off of. A generator streams realistic logs into
Cribl over syslog; a pre-seeded pipeline shapes them; processed events
land in `./output/` as JSON you can inspect with `cat`.

```sh
podman-compose -f docker-compose.demo.yml up -d
./smoke-test.sh                # asserts the whole flow end to end
```

## Data flow

```
log-generator ──syslog tcp 5140──> in_demo_syslog
                                        │
                                  demo_logs pipeline
                                    ├─ serde: extract JSON app events
                                    ├─ drop:  level == debug
                                    ├─ regex_extract: access-log fields
                                    ├─ mask:  redact email addresses
                                    └─ eval:  numerify status, tag event
                                        │
                              out_demo_fs ──> ./output/<host>/*.json
```

Three log shapes are generated (`generator/generate_logs.py`, stdlib
only, deterministic): nginx combined access logs (`web01`), JSON
application events with customer emails (`app01`), and sshd auth lines
(`auth01`). The debug events and emails exist on purpose — the pipeline
must drop the former and redact the latter, and `smoke-test.sh` fails if
it doesn't.

## Building off it

All Cribl config is plain files under `config/` (mounted at
`/opt/cribl/local/cribl`):

- `inputs.yml` — the syslog source; add HEC, TCP JSON, Kafka, ... here.
- `outputs.yml` — the filesystem destination; swap for Splunk, Elastic,
  S3, etc. (see `../custom-pipelines/` for terraform-driven variants).
- `pipelines/demo_logs/conf.yml` — the functions; edit, then
  `podman restart cribl-demo` and watch `./output/` change.
- `pipelines/route.yml` — routing; everything non-demo goes to devnull.

The UI at http://127.0.0.1:19001 (admin / admin on first boot — change
it) edits the same files, so UI changes show up in `git diff`. Runtime
state Cribl writes into `config/` (`auth/`, `cribl.inited`) is
gitignored.
