# Splunk integrations

Two independent projects. Neither depends on the other at runtime.

| Project | What it is |
|---|---|
| [`datagen/`](datagen/) | Generates realistic sample log data for any Splunk environment, and delivers it over whichever path you need. Standalone tool, no Splunk app required. |
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
  planning/        working notes, untracked
```

`planning/` is ignored at any depth. Status and roadmaps live there rather
than in a committed README, which should say what the tool does today.
