---
title: "Splunk Hardening Toolkit"
subtitle: "What this directory is"
author: "Security Control Assessment"
date: "2026-11-09"
---

# Splunk Hardening Toolkit

Splunk Enterprise collects logs from many systems, stores them, and lets people search
them. In an accreditation it is usually the central log server - the place audit records
go so they can be kept, protected and reviewed.

This toolkit assesses a Splunk Enterprise instance against the DISA Security Requirements
Guides that govern it, and emits DISA checklists in both formats: `.ckl` for STIG Viewer
2.x and `.cklb` for STIG Viewer 3.x. It also produces an evidence bundle and a record of
how each determination was reached.

Two baselines govern, 253 requirements between them. Only one of the two has DISA
precedent for this product; including the other was our determination. `docs/03-baseline-selection.md`
states which is which and on what basis.

## Status

Last full run: `epo-uat-indexer`, Splunk Enterprise 10.4.2. All 253 requirements have a
status - **141 Open, 79 Not a Finding, 33 Not Reviewed**. Having a status is not the
same as being verified; the table says which is which.

**Not ready to submit as a finished assessment.** 60 Open findings do not yet cite
vendor evidence.

| # | Item | Status |
|---|---|---|
| 1 | Read-only collection from the instance | **Done** |
| 2 | Decision engine, rule file per requirement | **Done** |
| 3 | Checklist emission, `.ckl` and `.cklb` | **Done** |
| 4 | Evidence bundle, manifest, secret redaction | **Done** |
| 5 | Setting-family resolution (`[role_<roleName>]` etc.) | **Done** |
| 6 | Container and bare-metal execution, one code path | **Done** |
| 7 | Documentation set | **Done** |
| 8 | Vendor confirmation of criteria | **Partial** - 100 of 253; 81 of 141 Open findings |
| 9 | Corrections from verification applied | **Partial** - 58 applied, 47 need reading |
| 10 | Baseline selection | **Done** - 2 apply, 10 determined not applicable |
| 11 | Specification set matched to product version | **Done** - rebuilt on 10.4.2 |
| 12 | `checks.tsv` derived from rule files | **Not started** - tool written, not applied |
| 13 | STIG Viewer re-import handoff | **Not started** - defect known, worked around by hand |
| 14 | Send results to Splunk, RMF app dashboards | **Not started** - planned only |
| 15 | Implementation: risk model | **Done** - `docs/RISK-MODEL.md` |
| 16 | Implementation: checkpoint and apply design | **Design only** - no code |
| 17 | Implementation: apply tooling | **Paused** - deliberately, until assessment is settled |

### The gaps in one line each

- **153 requirements rest on the benchmark text alone**, never confirmed against vendor
  documentation. Of the 141 Open findings, 81 cite evidence and 60 do not.
- **The baseline is settled.** Two SRGs apply, ten were determined not applicable, and
  comparable product STIGs support including the Web Server SRG.
- **4 requirements had every criterion contradicted** by vendor documentation. Left
  Open rather than silently made Not Reviewed. They need rewriting.
- **27 Splunk-shipped sourcetypes set `DATETIME_CONFIG = NONE`**, which the strict
  reading reports as findings. Real finding or vendor default - unresolved.
- **Nothing in `implement/` is executable.** It is three design documents.

### Baselines evaluated

An SRG governs a product that **performs** that function as a service to others - not
one that merely uses or contains the capability. Splunk authenticates users but is not
an authentication service; it stores data but is not a database; it exposes an API but
is not an API platform. That rule settles every candidate below.

| Baseline | Status | Basis |
|---|---|---|
| Central Log Server SRG V3R5 | **Applies** - 127 reqs, assessed | Splunk is a central log server. All 37 rules of DISA's Splunk STIG derive from it |
| Web Server SRG V4R5 | **Applies** - 126 reqs, assessed | Splunk Web serves a browser UI on 8000; splunkd serves HTTP on 8089. DISA's Splunk STIG drew nothing from it, but the STIGs for Dragos, Tanium and Xylok - comparable platforms with web UIs - each cite Web-Server-only requirements (8, 15, 16). The precedent supports inclusion; the Splunk STIG is the outlier |
| Application Security and Development STIG | **Not applicable** | Governs applications the organization develops. Splunk is commercial software. *Carve-out: custom Splunk apps written in-house are developed code and would fall under it* |
| General Application (GAPP) SRG | **Not applicable** | A general application baseline is the fallback where no technology-specific SRG exists. Central Log Server is the specific one and supersedes it |
| Application Programming Interface (API) SRG | **Not applicable** | Governs API management platforms and gateways. splunkd's REST interface is an application function, already governed as an HTTP listener under Web Server |
| Application Server SRG | **Not applicable** | Governs middleware hosting independently deployed applications - Tomcat, JBoss, WebLogic. Splunk apps are configuration bundles, not deployed applications |
| Authentication, Authorization and Accounting SRG | **Not applicable** | Governs AAA services - RADIUS, TACACS+, identity providers. Splunk authenticates its own users and consumes LDAP or SAML; it provides AAA to nothing |
| Database SRG | **Not applicable** | Governs database management systems. Splunk's index is a proprietary time-series store with no RDBMS and no SQL engine |
| Intrusion Detection and Prevention System SRG | **Not applicable** | Splunk inspects no traffic and blocks nothing. A SIEM consumes IDS output; Enterprise Security correlates and alerts, still not in-line detection |
| General Purpose Operating System SRG | **Not applicable** | Governs an operating system. The host is a separate asset with its own product STIG |
| General Application Draft SRG V1R0.1 | **Tracking only** | A draft is not an authorization baseline |
| 27 further SRGs | **Not applicable** | Network devices, cloud, containers, DNS, voice, endpoint management, virtualization, mainframe, operational technology |

**Conclusion: Central Log Server SRG and Web Server SRG are the applicable baselines.**
253 requirements, and the baseline question is closed.

Including the Web Server SRG was initially our own determination, since DISA's Splunk
STIG drew nothing from it. Comparing the product STIGs held in `stig_viewer/library`
settles it: Dragos, Tanium and Xylok - security platforms with web management
interfaces, like Splunk - each derive rules from requirements that exist **only** in
the Web Server SRG (8, 15 and 16 respectively). Splunk's STIG is the one that cites
none. The precedent supports inclusion.



## It reads. It does not change anything.

Every observation comes from `splunk btool`, the command that prints the configuration
actually in effect and the file each value came from. It reads configuration and writes
none. There is no code path in the assessment module that modifies an instance.

Two further properties follow from that, and both matter in practice:

- **No credentials are needed.** Reading configuration needs no account and no cached
  session, so an assessment needs no credentials on the system it assesses.
- **No change request is needed.** Nothing is written, so this can run on a production
  instance.

Applying a hardening change is a separate module, deliberately. See `implement/`, which is
paused.

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

Steps 3 and 4 read only what steps 1 and 2 wrote. They need no Splunk, no credentials and
no network. `assess.sh` and `evaluate.sh` each print the paths they wrote; copy `HOST` and
`STAMP` from that output rather than guessing.

Two notes that save a wasted run:

- **`evaluate.sh` exits 1 when any requirement is Open.** That is the result, not an
  error. Do not let a wrapper script read it as a failure.
- **Pass `--verdicts` to `emit-checklist.py`.** Without it the checklist is complete and
  reports every requirement `Not_Reviewed`, because the decisions live in the verdicts
  file from step 3.

For a containerized Splunk, `assess/bin/in-container.sh <container> <script> [args]`
copies the toolkit in, runs it there as the account that owns the installation, and copies
the results back. It is the same scripts, not a second code path.

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

`assess/out/` is gitignored for a reason. The evidence bundle retains the raw `btool`
output so a finding can be re-derived from it, which is roughly 26 MB per run and
unredacted by design.

Settings are read against a version-matched specification set in
`../splunk-spec-files-10.4.2`, a sibling of this directory.
`bin/build-conf-glossary.py` prefers the highest-numbered `splunk-spec-files-*` directory
it finds and honors `SPLUNK_SPEC_DIR`.

## Where to read next

**`docs/00-START-HERE.md`.** It indexes the document set in reading order: what Splunk is,
how a status is reached, which baselines govern and why, what the evidence establishes,
and how to open and keep a checklist.
