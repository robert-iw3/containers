---
title: "Splunk Hardening Toolkit"
subtitle: "Evidence and chain of custody"
author: "Security Control Assessment"
date: "2026-11-09"
---

# Evidence and Chain of Custody

Splunk Enterprise is an application that collects and searches log data. Its
behavior is set by configuration files. The command `splunk btool` prints the
configuration the instance will actually use and names the file each value came
from. Every observation in an assessment comes from `btool`, which reads
configuration and writes none. A run changes nothing on the instance.

## What a run produces

One assessment run (`assess/bin/assess.sh`) writes four kinds of artifact under
`assess/out/`.

| Artifact | What it is |
|---|---|
| `assessment-<host>-<stamp>.tsv` | The results table: one row per check row observed. |
| `evidence-<host>-<stamp>/` | The raw `btool` output, retained, with a manifest. |
| `MANIFEST.txt` and `MANIFEST.txt.sha256` | Chain of custody, with a SHA-256 over every file in the bundle. |
| `splunk-<host>.ckl` and `.cklb` | The DISA checklists, written by `assess/bin/emit-checklist.py`. |

The results table has eleven columns. Two carry most of the weight.
`precedence` names the configuration layer that supplied the winning value,
because `$SPLUNK_HOME/etc/system/local` outranks every installed app.
`observed_line` holds the `btool` line verbatim.

Deciding status is a separate step. `assess/bin/evaluate.sh` reads the results
table and writes `verdicts-<stamp>.tsv`: the requirement, its status, the
confidence, and the reason. For the instance assessed so far
(`epo-uat-indexer`, Splunk Enterprise 10.4.2, build 33c3bf42cd73), the 253
requirements came out 120 Open, 94 Not a Finding, and 39 Not Reviewed.

## Why the raw output is kept

The bundle retains the raw `btool` output: one file per configuration file read,
33 of them, plus a file of instance facts such as the version, the build, and
the account that owns the installation. Each file is digested with SHA-256,
recorded in the manifest beside the exact command that produced it. Any finding
can then be recomputed from the evidence, and an edit to the results table
detected.

A bundle is about 26 MB: roughly 9 MB of raw `btool` output and 17 MB of the
flattened form the results table is joined against.

## Redaction

Values of credential-bearing settings are replaced during collection, before
anything derived from them is written. A redacted value carries the length and
nothing else: `<redacted: 59 chars>`.

A value is redacted on either of two tests:

- **The setting name is known to carry a secret.** `sslPassword`,
  `sslKeysfilePassword`, `pass4SymmKey`, `bindDNpassword`, `privKeyPassword`,
  `sslRootCAPathPassword`.
- **The value is shaped like an encrypted secret.** Splunk writes encrypted
  values with a `$7$` style prefix, and some settings hold a long `AQ...`
  string. Either shape is redacted whatever the setting is called.

The setting name and the file it came from are kept; only the value is withheld.

**A policy setting whose name contains "password" stays readable.**
`minPasswordLength` and `expirePasswordDays` are password *policy*, and their
values are the finding. The match is never on the substring.

Redaction reaches the results table and everything generated from it, including
both checklists, so a checklist can be mailed or attached to a package. The
retained raw output is **unredacted by design**, so that a finding can be
re-derived from it. The manifest records that, and tells the reader to protect
the directory at the system's own level.

## Why `assess/out/` is never committed

`assess/out/` is in `.gitignore`. The bundle is unredacted: committing it would
publish a TLS private key passphrase and the cluster shared secret into a
history that cannot be rewritten cleanly once pushed. It is also about 26 MB per
run, and every file in it is reproducible by running the toolkit again.

## Vendor verification as evidence

The specification file shipped with the product can disagree with the vendor's
published documentation, so a criterion built from that file alone can be wrong.
The settings behind the criteria were looked up in the vendor's own
configuration-file reference. Where a setting could be exercised, it was
exercised on a running instance.

`bin/import-vendor-verification.py` reads the working journals and writes
`assess/inventory/vendor-verification.json`. The store currently holds 169
settings across ten configuration files. Each entry records:

- the configuration file, stanza and setting
- whether the setting exists in the running version at all
- the vendor page, by URL, and what the vendor says there
- whether the setting was read, applied and accepted, applied and rejected, or
  not exercised
- a verdict on the criterion, and a correction where one applies

Of the 169 settings, 168 carry a vendor page citation. All ten configuration
files have at least one recorded disagreement between the vendor's documentation
and the product's specification file.

The import is idempotent. A journal is append-only, so re-importing one changes
nothing. A later journal updates an earlier entry for the same setting; that is
how a correction lands.

`assess/bin/apply-verification.py` carries the verification into the rule files
in `assess/rules/`. It writes a fenced block that a later run removes exactly,
so the result is a function of the rules and the store, not of how many times
the applier has run. The block holds one `vendor:` pointer line per setting:
configuration file, stanza, setting, URL. The vendor's prose stays in the store,
held once. `emit-checklist.py` joins the two at emit time and renders a
**VENDOR SOURCES FOR THIS CRITERION** block in the checklist: the page, what it
says, and whether the setting was exercised on this instance.

163 of the 253 requirements now carry at least one vendor citation. 58 criteria
were corrected where verification found they tested the wrong setting, the wrong
operator, or the wrong thing entirely.

### Confidence

Each requirement carries one of three confidence levels. The checklist states
the basis under **BASIS OF THIS STATUS**.

| Confidence | Means |
|---|---|
| `derived` | Built from the benchmark check text and the configuration specification shipped with the product. At least one setting it tests has not been confirmed against the vendor's documentation. |
| `documented` | Every setting the criterion tests was confirmed against the vendor's published documentation, and the page is cited in the finding. |
| `tested` | As `documented`, and the behavior was exercised on a running instance: the value was applied and the product accepted or rejected it. |

A requirement is recorded `documented` only when *every* setting it tests was
confirmed; one unconfirmed setting holds the whole requirement at `derived`.

The current distribution is 11 tested, 89 documented, 153 derived.

## Withdrawn criteria are kept, not deleted

Where the vendor documentation contradicted a criterion outright, the criterion
is withdrawn. It stays in the rule file as `retired_check:` with the reason, and
the checklist lists it under **CRITERIA WITHDRAWN AFTER VERIFICATION**. The
record shows why it was dropped and on what authority.

50 criteria across 37 requirements were withdrawn this way.

A withdrawal is **never applied if it would leave a requirement with no
criterion at all**. A requirement with no criterion evaluates to Not Reviewed.
Where every criterion for a requirement was contradicted, the applier keeps them
and prints the requirement under `NEEDS READING`, for a person to resolve.

Corrections that could not be expressed as a single criterion in the evaluator's
syntax are written to a deferral report, to be read by hand. A criterion the
evaluator cannot parse fails silently.

## What the chain of custody establishes

The manifest records who collected the evidence, on what host, by which command,
at what time, and a SHA-256 over every file. Its own digest is written beside it
in `MANIFEST.txt.sha256`, so a reader carries forward one value.

That makes the evidence three things:

- **Attributable.** The manifest names the account, the host, the Splunk
  version, the toolkit, and the check data with its digest.
- **Reproducible.** Every command is recorded verbatim. The same commands can be
  run again, and the findings recomputed from the retained output.
- **Tamper-evident.** Altering any file changes its digest, so a reader can
  detect that the evidence or the results were changed after collection.

It is **not non-repudiable**, and the manifest says so where it is unsigned.
Tamper-evident means an alteration can be *detected*. Non-repudiable means the
collector cannot later deny having produced the evidence. The collecting process
computes the digest, so it can also replace it. Only a signature over the
manifest, made with a key that process does not hold, forecloses repudiation.

`assess.sh --sign-with KEY` signs the manifest and writes a `.sig` beside it.
Use a key held outside the collecting process. Without a signature the manifest
prints:

```
SIGNATURE
unsigned. This manifest is tamper-evident, not non-repudiable: no key
outside the collecting process attests to it.
```

## What to do with the bundle

1. **Verify it first.** Recompute the manifest digest with
   `sha256sum MANIFEST.txt` and compare it to `MANIFEST.txt.sha256`. Then check
   any file you intend to rely on against its row in the manifest table. If a
   `.sig` is present, verify it with the matching public key.
2. **Check the header before the findings.** The manifest names the host, the
   Splunk version and build, the account that collected, and the digest of the
   check data used. A different version or different check data makes it a
   different assessment.
3. **Re-derive anything you doubt.** Open the `.raw` file for the configuration
   file in question and read it. Every finding points at a setting, a file and a
   configuration layer; all three are in the raw output.
4. **Follow a citation when the status turns on a criterion.** The vendor page
   is in the finding. Confirm it independently.
5. **Read the confidence line.** A `derived` status rests on the specification
   file shipped with the product, not on the vendor's documentation. Treat it as
   a first reading and verify before it is relied on.
6. **Handle the bundle as sensitive.** It is unredacted. Store it with the
   assessment package at that package's classification. Do not attach it where a
   checklist would do; the checklists are redacted and the bundle is not.
