---
title: "Checklists and STIG Viewer"
subtitle: "Producing, opening and keeping an assessment checklist"
author: "Security Control Assessment"
date: "2026-11-10"
---

# Checklists and STIG Viewer

The assessment emits a checklist in both DISA formats from one result set.

## Two formats

| File | Opened by | Status values |
|---|---|---|
| `.ckl` | STIG Viewer 2.x | `NotAFinding`, `Open`, `Not_Applicable`, `Not_Reviewed` |
| `.cklb` | STIG Viewer 3.x | `not_a_finding`, `open`, `not_applicable`, `not_reviewed` |

The vocabularies differ, and one format's values in the other's file produce a file the
viewer rejects. Both files come from the same results.

## Producing one

```
assess/bin/emit-checklist.py \
    --results  assess/out/HOST/assessment-HOST-STAMP.tsv \
    --manifest assess/out/HOST/evidence-HOST-STAMP/MANIFEST.txt \
    --out      assess/out/HOST
```

`--manifest` is optional. Pass it: it supplies the chain of custody written into every
finding's comments.

Benchmark identity is read from the XCCDF: title, version, release date and rule count. An
earlier version transcribed it into the code and reported a benchmark date three months
wrong.

## What is in a finding

`btool` is the Splunk command that prints the configuration in effect and the file each
value came from.

| Field | Contents |
|---|---|
| Finding details | Every setting in effect, with its literal value. The file that supplied each value, and the layer that file belongs to. The verbatim `btool` line. Settings not present, listed separately as taking the product default. |
| Comments | The applicability determination and its evidence grade. The mechanism. The assessment method. Anything the application cannot reach. The chain of custody: when, by which account, on what host, which Splunk version and build, and the digest of the evidence manifest. |

Where a value comes from `etc/system/local`, the finding says so. That layer outranks every
app, so a hardening change written into an app cannot override it.

Credential values are redacted; a checklist is shared, and the TLS private key passphrase is
recoverable from its stored form. The key name and its source file are kept. Password
*policy* settings are not redacted.

## Opening one

A containerized STIG Viewer lives at `containers/stig_viewer`. It is general purpose, not
specific to this toolkit.

```
cd containers/stig_viewer
./run.sh /path/to/splunk-HOST.cklb
```

The first run builds a minimal Electron runtime and extracts the viewer from the vendor
archive named in `stig-viewer.conf`. That file holds all configuration, and every value in it
can be overridden by an environment variable of the same name.

### Benchmarks

The viewer needs the benchmarks the checklist refers to.

```
./fetch-library.sh --zip ~/Downloads/U_Central_Log_Server_V3R5_SRG.zip
./fetch-library.sh --list
```

`fetch-library.sh` ingests any DISA distribution: a single SRG or STIG archive, or the
quarterly compilation, which is archives inside an archive. It finds every XCCDF however
deeply nested and catalogs them by reading the documents, not their file names. `--url`
downloads an archive first, printing its name and size before it starts. There is no default
URL; the compilation's name changes every quarter.

## Keeping one

`containers/stig_viewer/checklists` is mounted read-write, so statuses and comments set in
the viewer are saved on the host and survive the container. The viewer's own state, such as
window layout and recent files, persists the same way. The viewer binary and the benchmark
library are mounted read-only.

`run.sh` copies a checklist named on the command line into that directory and opens the copy.
A newer file left elsewhere does not reach the viewer. Pass it to `run.sh` again, or replace
the copy in `checklists`.

## Re-assessing

Re-running the assessment produces a fresh result set, and re-emitting produces a fresh
checklist. Regeneration does not merge into a worked checklist: statuses and comments a person
set are lost, because the generator cannot tell a considered adjudication from a default.

Re-emit to a new file and compare it. Never overwrite a checklist somebody has worked on. No
merge exists yet that keeps human adjudication and refreshes only the observed configuration.
