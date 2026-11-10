---
title: "Splunk Hardening Toolkit"
subtitle: "Start here"
author: "Security Control Assessment"
date: "2026-11-09"
---

# Splunk Hardening Toolkit

This toolkit assesses a Splunk Enterprise instance against the Security Requirements
Guides that govern it, and produces the artifacts an assessment package needs: DISA
checklists, an evidence bundle, and a record of how each determination was reached.

**It reads. It does not change anything.** Every observation comes from `splunk btool`,
which reads configuration and writes none. There is no code path in the assessment module
that modifies an instance, so it can run on a production system without a change request.

## What you get

| Artifact | For |
|---|---|
| `.ckl` and `.cklb` checklists | an assessor, opened in STIG Viewer |
| Evidence bundle with a manifest | proving where every finding came from |
| Applicability matrix | the Authorizing Official: what applies, and on what evidence |

## Five minutes

Four steps. The first two run on the Splunk instance. The last two are pure text over
what the first two wrote, so they run wherever you read the results - no Splunk, no
credentials, no network.

```
# 1. is the instance sound enough to assess
assess/bin/health-check.sh --baseline

# 2. read the configuration, keep the evidence
assess/bin/assess.sh

# 3. decide each requirement against the rule files
assess/bin/evaluate.sh \
    --results assess/out/HOST/assessment-HOST-STAMP.tsv \
    --out     assess/out/HOST

# 4. turn the results and the decisions into checklists
assess/bin/emit-checklist.py \
    --results  assess/out/HOST/assessment-HOST-STAMP.tsv \
    --verdicts assess/out/HOST/verdicts-STAMP.tsv \
    --manifest assess/out/HOST/evidence-HOST-STAMP/MANIFEST.txt \
    --out      assess/out/HOST
```

`HOST` and `STAMP` are not placeholders you invent: `assess.sh` prints the exact paths it
wrote, and `evaluate.sh` prints the verdict file it wrote. Copy them from that output.

Two things about those commands are easy to get wrong.

**`evaluate.sh` exits 1 when any requirement is Open.** That is the result, not an error.
It writes its verdicts into the directory given by `--out`, defaulting to the directory
the results file is in. A script wrapping it must not treat exit 1 as a failed run.

**`--verdicts` is not optional in practice.** `emit-checklist.py` accepts results without
it, and then reports every requirement `Not_Reviewed` - a complete checklist that assesses
nothing. The decisions come from step 3, so step 3 cannot be skipped.

Assessing a containerized Splunk is the same operation. `assess/bin/in-container.sh`
copies the toolkit in, runs it there as the account that owns the installation, and
copies the results back:

```
assess/bin/in-container.sh <container> health-check.sh --baseline
assess/bin/in-container.sh <container> assess.sh
```

Steps 3 and 4 then run on the host, against the results that came back.

There is deliberately only one code path. The scripts always run on the instance they
assess, so a container run exercises the same code as a host install rather than a
parallel implementation that is never tested where it matters.

## The documents

Read in this order if the toolkit is new to you. Each answers one question.

| Document | Answers |
|---|---|
| `01-splunk-for-assessors.md` | What is Splunk, what are its parts, how is it configured? |
| `02-how-it-decides.md` | How does it decide whether a requirement is met? |
| `03-baseline-selection.md` | Which requirements govern, and why those? |
| `04-evidence-and-custody.md` | What evidence is produced, and what does it establish? |
| `05-checklists-and-stig-viewer.md` | How do I open, work and keep a checklist? |
| `applicability-matrix.md` | Which requirements apply to Splunk, and why? (generated) |
| `RISK-MODEL.md` | When is a change too risky to automate? (implementation module) |

Skip `01` if you already know Splunk. Read `03` before quoting a count at anyone: two
baselines govern, 253 requirements between them, and only one of the two has DISA
precedent for this product. `03` states which, and on what basis the other was included.

## What it does not do

**It does not change configuration.** Applying a hardening change is a separate module
with a separate risk model, because deciding what is true and deciding what to alter are
different problems with different consequences for getting them wrong.

**It does not claim a requirement is met without a criterion.** A requirement with no
basis for judgment is reported `Not_Reviewed`, with the reason recorded. A checklist
that reports a requirement as satisfied because nobody assessed it is the failure a
checklist exists to prevent.

**It assesses the application layer alone.** Where a requirement's objective extends past
what Splunk itself can configure, the remainder is named in the finding rather than
counted against the application.
