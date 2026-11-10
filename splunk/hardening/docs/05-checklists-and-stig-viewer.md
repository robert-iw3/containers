---
title: "Checklists and STIG Viewer"
subtitle: "Producing, opening and keeping an assessment checklist"
author: "Security Control Assessment"
date: "2026-11-10"
---

# Checklists and STIG Viewer

The assessment produces a checklist in both DISA formats from one result set. This
describes what is in them, how to open them, and how to keep one over the weeks an
assessment actually takes.

## Two formats, two vocabularies

| File | Opened by | Status values |
|---|---|---|
| `.ckl` | STIG Viewer 2.x | `NotAFinding`, `Open`, `Not_Applicable`, `Not_Reviewed` |
| `.cklb` | STIG Viewer 3.x | `not_a_finding`, `open`, `not_applicable`, `not_reviewed` |

The vocabularies differ, and reusing one for the other produces a file the viewer
rejects. Both are emitted from the same results so they cannot disagree.

## Producing one

```
assess/bin/emit-checklist.py \
    --results  assess/out/HOST/assessment-HOST-STAMP.tsv \
    --manifest assess/out/HOST/evidence-HOST-STAMP/MANIFEST.txt \
    --out      assess/out/HOST
```

The manifest is optional but should be given: it is what puts the chain of custody into
every finding's comments.

Benchmark identity - title, version, release date and rule count - is read from the
XCCDF, never from a table in the code. A transcribed copy of a vendor's metadata goes
stale, and did: an earlier version carried a benchmark date three months wrong.

## What is in a finding

**Finding details** carry the exact configuration observed:

- every setting in effect, with its literal value;
- the file that supplied each value, and which layer that file belongs to;
- the verbatim `btool` line, so a finding quotes what was read rather than a
  reconstruction of it;
- settings not present, listed separately as taking the product default, so absence is
  recorded rather than looking like an omission.

Where a value comes from `etc/system/local` the finding says so explicitly, because that
layer outranks every app and a hardening change written into an app cannot override it.

**Comments** carry the applicability determination with its evidence grade, the mechanism,
the assessment method, anything the application cannot reach, and the chain of custody:
when, by which account, on what host, which Splunk version and build, and the digest of
the evidence manifest.

**Credential values are redacted.** A checklist is shared, and the TLS private key
passphrase is recoverable from its stored form. The key name and its source file are
kept, because those are the assessable facts; only the value is withheld. Password
*policy* settings stay readable - redacting those would remove exactly what an assessor
needs.

## Opening one

A containerized STIG Viewer lives at `containers/stig_viewer`. It is general purpose and
not specific to this toolkit.

```
cd containers/stig_viewer
./run.sh /path/to/splunk-HOST.cklb
```

On first run it builds a minimal Electron runtime and extracts the viewer from the
vendor archive named in `stig-viewer.conf`. Configuration is in that one file, and every
value in it is overridable by an environment variable of the same name.

### Benchmarks

The viewer wants the benchmarks the checklist refers to:

```
./fetch-library.sh --zip ~/Downloads/U_Central_Log_Server_V3R5_SRG.zip
./fetch-library.sh --list
```

`fetch-library.sh` ingests any DISA distribution - a single SRG or STIG archive, or the
full quarterly compilation, which is archives inside an archive - finds every XCCDF
however deeply nested, and catalogs them by reading the documents rather than parsing
file names. `--url` downloads one first, and prints what it is about to fetch and its
size before it starts. No URL is assumed: the compilation's name changes every quarter.

## Keeping one

**Checklists persist on the host.** `containers/stig_viewer/checklists` is mounted
read-write, so statuses set and comments written in the viewer are saved outside the
container and survive it. The viewer's own state - window layout, recent files - persists
the same way. This is the point: a checklist is opened, worked, saved and reopened over
the weeks an assessment takes, and a tool that loses that on exit is not usable.

The viewer binary and the benchmark library are mounted read-only. Nothing the viewer
does should alter either.

## Re-assessing

Re-running an assessment produces a fresh result set, and re-emitting produces a fresh
checklist. **It does not merge into one an assessor has worked.** Statuses set and
comments written by a person are not preserved by regeneration, because the generator has
no way to tell a considered adjudication from a default.

Until a merge exists that keeps human adjudication and refreshes only the observed
configuration, re-emit to a new file and compare, rather than overwriting a checklist
somebody has worked on.
