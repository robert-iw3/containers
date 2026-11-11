# Splunk integrations

Two independent projects. Neither depends on the other at runtime.

| Project | What it is |
|---|---|
| [`datagen/`](datagen/) | Generates realistic sample log data for any Splunk environment, and delivers it over whichever ingest path you need. Standalone tool, no Splunk app required. |
| [`sigma/`](sigma/) | Converts Sigma detection rules into Splunk saved searches, and tests them against real data. Uses `datagen` to produce the data it tests with. |

## Layout

Both follow the same shape, so one is navigable from the other:

```
<project>/
  README.md        what it does and how to run it
  *.py *.ps1       the entry points an operator runs
  templates/       or pipelines/, config/ -- the declarative inputs
  bin/             helper tools that are not entry points
  admin/           scripts that configure a Splunk environment
  docs/            guides for the parts that cannot be scripted
  deploy/          installs something into a Splunk instance
  tests/           fixtures, including deliberately broken input
```

[`lib/`](lib/) holds what both projects share. `splunk-transport.sh` reaches
a Splunk instance over any substrate — bare metal, SSH, podman, docker, or a
Kubernetes pod — and reports whether a filesystem write on that substrate
survives the instance being replaced.
