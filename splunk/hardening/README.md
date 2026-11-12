---
title: "Splunk Hardening Toolkit"
subtitle: "What this directory is"
author: "Security Control Assessment"
date: "2026-11-09"
---

# Splunk Hardening Toolkit

Splunk Enterprise collects logs from many systems, stores them, and lets people search
them. In an accreditation it is the central log server: where audit records are kept,
protected and reviewed.

This toolkit assesses an instance against the DISA Security Requirements Guides (SRGs)
that govern it. It emits DISA checklists in both formats, `.ckl` for STIG Viewer 2.x and
`.cklb` for STIG Viewer 3.x, plus an evidence bundle and a record of how each
determination was reached.

Two baselines govern, 253 requirements between them. One has DISA precedent for this
product; including the other was our determination. `docs/03-baseline-selection.md` says
which is which.

## Status

Last full run: `epo-uat-indexer`, Splunk Enterprise 10.4.2. All 253 requirements have a
status: **120 Open, 94 Not a Finding, 39 Not Reviewed**. A status is not a verified
status; the table says which items are verified.

**Not ready to submit as a finished assessment.** 49 Open findings do not cite vendor
evidence.

| # | Item | Status |
|---|---|---|
| 1 | Read-only collection from the instance | **Done** |
| 2 | Decision engine, rule file per requirement | **Done** |
| 3 | Checklist emission, `.ckl` and `.cklb` | **Done** |
| 4 | Evidence bundle, manifest, secret redaction | **Done** |
| 5 | Setting-family resolution (`[role_<roleName>]` etc.) | **Done** |
| 6 | Container and bare-metal execution, one code path | **Done** |
| 7 | Documentation set | **Done** |
| 8 | Vendor confirmation of criteria | **Partial** - 100 of 253; 71 of 120 Open findings |
| 9 | Corrections from verification applied | **Done** - 55 distinct corrections; 49 in full, 4 in part, 2 withheld with reasons |
| 10 | Baseline selection | **Done** - 2 apply, 10 determined not applicable |
| 11 | Specification set matched to product version | **Done** - rebuilt on 10.4.2 |
| 12 | `checks.tsv` derived from rule files | **Done** - `derive-checks.py --merge`; 0 criteria decide on uncollected settings |
| 13 | STIG Viewer staleness handoff | **Done** - `run.sh` detects a running window and offers to replace it; `--replace` for non-interactive |
| 14 | Applying changes (a separate module) | **Not started** - assessment only; nothing in this toolkit alters an instance |

### Gaps

- **153 requirements rest on the benchmark text alone**, never confirmed against vendor
  documentation. Of the 120 Open findings, 71 cite evidence and 49 do not.
- **The baseline is settled.** Two SRGs apply, ten were determined not applicable.
- **4 requirements had every criterion contradicted** by vendor documentation. They remain
  Open and need rewriting.
- **27 Splunk-shipped sourcetypes set `DATETIME_CONFIG = NONE`.** The strict reading
  reports them as findings. Real finding or vendor default: unresolved.
- **Nothing applies a change.** Making one is a separate module that does not exist yet.

### Baselines evaluated

An SRG governs a product that **performs** that function as a service to others, not one
that merely uses or contains the capability. That rule settles every candidate below.

| Baseline | Status | Basis |
|---|---|---|
| Central Log Server SRG V3R5 | **Applies** - 127 reqs, assessed | Splunk is a central log server. All 37 rules of DISA's Splunk STIG derive from it |
| Web Server SRG V4R5 | **Applies** - 126 reqs, assessed | Splunk Web serves a browser UI on 8000; splunkd serves HTTP on 8089. DISA's Splunk STIG drew nothing from it. The STIGs for Dragos, Tanium and Xylok in `stig_viewer/library`, comparable platforms with web management interfaces, each cite Web-Server-only requirements (8, 15 and 16 respectively). That precedent supports inclusion |
| Application Security and Development STIG | **Not applicable** | Governs applications the organization develops. Splunk is commercial software. *Carve-out: custom Splunk apps written in-house are developed code and would fall under it* |
| General Application (GAPP) SRG | **Not applicable** | A general application baseline is the fallback where no technology-specific SRG exists. Central Log Server is the specific one and supersedes it |
| Application Programming Interface (API) SRG | **Not applicable** | Governs API management platforms and gateways. splunkd's REST interface is an application function, already governed as an HTTP listener under Web Server |
| Application Server SRG | **Not applicable** | Governs middleware that hosts independently deployed applications: Tomcat, JBoss, WebLogic. Splunk apps are configuration bundles, not deployed applications |
| Authentication, Authorization and Accounting SRG | **Not applicable** | Governs AAA services: RADIUS, TACACS+, identity providers. Splunk authenticates its own users and consumes LDAP or SAML. It provides AAA to nothing |
| Database SRG | **Not applicable** | Governs database management systems. Splunk's index is a proprietary time-series store with no RDBMS and no SQL engine |
| Intrusion Detection and Prevention System SRG | **Not applicable** | Splunk inspects no traffic and blocks nothing. A SIEM consumes IDS output. Enterprise Security correlates and alerts, which is not in-line detection |
| General Purpose Operating System SRG | **Not applicable** | Governs an operating system. The host is a separate asset with its own product STIG |
| General Application Draft SRG V1R0.1 | **Tracking only** | A draft is not an authorization baseline |
| 27 further SRGs | **Not applicable** | Network devices, cloud, containers, DNS, voice, endpoint management, virtualization, mainframe, operational technology |

**Central Log Server SRG and Web Server SRG are the applicable baselines**, 253
requirements. The baseline question is closed.

## Read-only operation

Every observation comes from `splunk btool`, the command that prints the configuration in
effect and the file each value came from. No code path in the assessment module modifies
an instance. Two things follow:

- **No credentials are needed.** Reading configuration needs no account and no cached
  session.
- **No change request is needed.** Nothing is written, so this can run on a production
  instance.

Applying a change is a separate module, `implement/`, which is paused.

## Quickstart

```
# 1. is the instance sound enough to assess       (on the Splunk instance)
assess/bin/health-check.sh --baseline

# 2. read the configuration, keep the evidence    (on the Splunk instance)
assess/bin/assess.sh

# 3. decide each requirement against the rules    (anywhere)
assess/bin/evaluate.sh --results assess/out/HOST/assessment-HOST-STAMP.tsv \
                       --out     assess/out/HOST

# 4. emit the checklists                          (anywhere)
assess/bin/emit-checklist.py \
    --results  assess/out/HOST/assessment-HOST-STAMP.tsv \
    --verdicts assess/out/HOST/verdicts-STAMP.tsv \
    --manifest assess/out/HOST/evidence-HOST-STAMP/MANIFEST.txt \
    --out      assess/out/HOST
```

Steps 3 and 4 read only what steps 1 and 2 wrote: no Splunk, no credentials, no network.
`assess.sh` and `evaluate.sh` print the paths they wrote; copy `HOST` and `STAMP` from
that output.

Two notes:

- **`evaluate.sh` exits 1 when any requirement is Open.** That is the result, not an
  error; do not let a wrapper script read it as a failure.
- **Pass `--verdicts` to `emit-checklist.py`.** The decisions live in that file from step
  3. Without it the checklist is complete and reports every requirement `Not_Reviewed`.

For a containerized Splunk, `assess/bin/in-container.sh <container> <script> [args]`
copies the toolkit in, runs it as the account that owns the installation, and copies the
results back. Same scripts, not a second code path.

## Layout

| Path | Holds |
|---|---|
| `docs/` | the document set. **Start at `docs/00-START-HERE.md`** |
| `assess/bin/` | the assessment scripts: health check, collect, evaluate, emit, container wrapper |
| `assess/rules/` | one file per requirement: the criterion it is judged against. Read at run time |
| `assess/inventory/` | the requirement data and vendor verification the scripts read |
| `assess/out/` | results, evidence and checklists. Generated, gitignored, **never commit it** |
| `benchmarks/` | the XCCDF benchmark documents the checklists are emitted against |
| `bin/` | build-time tools that produce the inventory and the documents |
| `lib/` | shared library both modules use: Splunk discovery and the privilege guard |
| `reference/` | the CCI list, the `.cklb` JSON schema, an example checklist |
| `implement/` | the implementation module. Paused; nothing applies a change yet |

`assess/out/` is gitignored: the evidence bundle keeps the raw `btool` output so a finding
can be re-derived, roughly 26 MB per run and unredacted by design.

Settings are read against the version-matched specification set in
`../splunk-spec-files-10.4.2`, a sibling of this directory.
`bin/build-conf-glossary.py` prefers the highest-numbered `splunk-spec-files-*` directory
it finds and honors `SPLUNK_SPEC_DIR`.

## Where to read next

`docs/00-START-HERE.md` indexes the document set in reading order: what Splunk is, how a
status is reached, which baselines govern, what the evidence establishes, and how to keep
a checklist.
