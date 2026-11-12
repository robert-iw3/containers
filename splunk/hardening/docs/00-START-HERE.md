---
title: "Splunk Hardening Toolkit"
subtitle: "Start here"
author: "Security Control Assessment"
date: "2026-11-09"
---

# Splunk Hardening Toolkit

Splunk Enterprise is a platform that indexes and searches log data. This toolkit
assesses one instance against the Security Requirements Guides that govern it, and
records how each determination was reached.

**It reads. It does not change anything.** Every observation comes from `splunk btool`,
which reads configuration and writes none. It needs no change request.

## What you get

| Artifact | For |
|---|---|
| `.ckl` and `.cklb` checklists | an assessor, opened in STIG Viewer |
| Evidence bundle with a manifest | proving where every finding came from |
| Applicability matrix | the Authorizing Official: what applies, and on what evidence |

## Quickstart

Steps 1 and 2 run on the Splunk instance. Steps 3 and 4 process what they wrote and need
no Splunk, no credentials and no network.

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

Do not invent `HOST` and `STAMP`. Copy them from the paths `assess.sh` and `evaluate.sh`
print.

**`evaluate.sh` exits 1 when any requirement is Open.** That is the result, not an error. A
wrapper must not treat it as failure. Verdicts go to `--out`, which defaults to the
directory holding the results file.

**Always pass `--verdicts`.** Without it, `emit-checklist.py` reports every requirement
`Not_Reviewed`. The decisions come from step 3.

`assess/bin/in-container.sh` assesses a containerized Splunk. It copies the toolkit in,
runs it as the account that owns the installation, and copies the results back:

```
assess/bin/in-container.sh <container> health-check.sh --baseline
assess/bin/in-container.sh <container> assess.sh
```

Steps 3 and 4 then run on the host. There is one code path: the scripts always run on the
instance they assess.

## The documents

Read in order if the toolkit is new to you. Skip `01` if you already know Splunk.

| Document | Answers |
|---|---|
| `01-splunk-for-assessors.md` | What is Splunk, what are its parts, how is it configured? |
| `02-how-it-decides.md` | How does it decide whether a requirement is met? |
| `03-baseline-selection.md` | Which requirements govern, and why those? |
| `04-evidence-and-custody.md` | What evidence is produced, and what does it establish? |
| `05-checklists-and-stig-viewer.md` | How do I open, work and keep a checklist? |
| `06-maintaining-the-rules.md` | Where is a change made, and what happens when an SRG is revised? |
| `applicability-matrix.md` | Which requirements apply to Splunk, and why? (generated) |

Read `03` before quoting a count: two baselines govern, 253 requirements between them,
and only one has DISA precedent for this product.

## What it does not do

**It does not change configuration.** Applying a hardening change is a separate module
with its own risk model.

**It does not report a requirement as met without a criterion.** A requirement nobody
assessed is `Not_Reviewed`, with the reason recorded.

**It assesses the application layer alone.** Where a requirement's objective extends past
what Splunk itself can configure, the finding names what is left for someone else to
answer.
