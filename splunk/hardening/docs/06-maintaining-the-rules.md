---
title: "Splunk Hardening Toolkit"
subtitle: "Maintaining the rules"
author: "Security Control Assessment"
date: "2026-11-11"
---

# Maintaining the Rules

`02-how-it-decides.md` states how a status is reached. This states where the
inputs live, who owns them, how a criterion is drafted, and what to do when DISA
publishes a new revision of a Security Requirements Guide.

## Where a configuration is made

A site that disagrees with how a requirement is assessed edits one rule file.
There are 253, one per requirement, at `assess/rules/<SRG-ID>.rule`. They are
plain text, read at run time, and edited with a text editor.

| Path | Holds | Written by | Generated |
|---|---|---|---|
| `assess/rules/*.rule` | one requirement's criterion and determination | a maintainer; scaffolded and refreshed by `build-rules.py` | no |
| `assess/inventory/criteria.json` | the conditions, contribution, external dependencies and finding statement for all 253 requirements | a maintainer | no |
| `assess/inventory/sca-determinations.json` | the determination, evidence grade, basis and assessment method | a maintainer | no |
| `assess/inventory/srg-applicability.json` | which baselines govern, and why | a maintainer | no |
| `assess/inventory/reference-findings.json` | the sunsetted STIG's settings and what became of them | a maintainer | no |
| `benchmarks/*.xccdf.xml` | the SRG documents, dropped in unmodified | DISA | no |
| `assess/inventory/srg-rules.json`, `srg-index.tsv` | the extracted requirements | `bin/extract-srg.py`, from `benchmarks/` | yes |
| `assess/inventory/cci-map.json` | each CCI and the controls it maps to | `bin/map-cci.py`, from `reference/CCI_List.xml` | yes |
| `assess/inventory/conf-glossary.tsv` | every declared setting | `bin/build-conf-glossary.py`, from the specification set | yes |
| `assess/inventory/vendor-verification.json` | the vendor evidence per setting | `bin/import-vendor-verification.py`, from verification journals | yes |
| `assess/inventory/checks.tsv` | the collection inventory | `assess/bin/derive-checks.py`, from the rule files | yes |
| `docs/applicability-matrix.md` | the applicability matrix | `bin/build-matrix.py` | yes |
| `assess/out/` | the output of a run. Gitignored, never committed | a run | yes |

### The two halves of a rule file

| The site owns | What it is |
|---|---|
| `check:` | a condition that decides the requirement. One per line |
| `retired_check:` | a condition withdrawn with its reason, kept rather than deleted |
| `decidable:` | `machine` or `manual` |
| `confidence:` | `derived`, `documented` or `tested` |
| `determination:`, `grade:` | whether the requirement applies, and on what evidence |
| `contribution:`, `governs:` | what the application does about it, and in which files |
| `external:` | the part of the objective Splunk does not carry |
| `manual_reason:` | why configuration cannot decide it |
| `citation:`, `finding:` | where the criterion came from, and the finding text |

| The benchmark owns | Refreshed in place by `assess/bin/build-rules.py` |
|---|---|
| the first comment line and the wrapped title | the requirement as DISA states it |
| `group:` | the V-number |
| `severity:`, `cat:` | `high`/`CAT I`, `medium`/`CAT II`, `low`/`CAT III` |
| `cci:` | the CCIs the requirement cites |
| `control_rev5:` | the SP 800-53 Rev 5 controls those CCIs map to |

A benchmark-owned field edited by hand is put back at the next refresh. Record a
disagreement with the SRG document in `citation:` instead.

Between the two halves sits a fenced block, written by
`assess/bin/apply-verification.py`:

```
# --- vendor verification: generated, do not edit by hand
corrected:       authorize.conf [role_<roleName>] change_audit equals enabled -> authorize.conf [role_admin] change_audit equals enabled
vendor:          authorize.conf [role_<roleName>] change_audit https://help.splunk.com/...
# --- end vendor verification
```

`corrected:` records what a criterion was corrected from. `vendor:` points at the
page a setting now rests on. A `retired_check:` inside the fence carries the
vendor's reason for withdrawing it. The corrected criterion itself sits above the
fence as an ordinary `check:` line, so that is the line to edit.

`assess/bin/evaluate.sh` reads only `id:`, `severity:`, `determination:`,
`decidable:`, `confidence:` and `check:`. A mistake in a `check:` line changes a
status. A mistake in `external:` or `finding:` changes the words
`assess/bin/emit-checklist.py` puts in the checklist, and no status.

### The scaffold and the derived files

`build-rules.py` scaffolds a requirement that appears in both `criteria.json` and
`srg-rules.json` with no rule file yet. `criteria.json` has no field for
`confidence:`, the fence, or a retired check, so a rule file is not a copy of it.
On the current tree, 168 of the 253 rule files differ from a scaffold, 99 of them
in the lines that decide a status. The generator reports both counts and writes
to neither.

`checks.tsv` lists the settings `assess/bin/assess.sh` reads off the instance, so
that collection cannot fall behind a corrected criterion. Regenerate it after
editing a `check:` line. `derive-checks.py` keeps the previous copy at
`checks.tsv.prev`.

`vendor-verification.json` holds, per setting, the vendor's own words, the page
URL, whether the setting exists in the version running, the result of exercising
it, a verdict, and the requirements it affects. 169 settings are in it today. A
rule file carries only a `vendor:` pointer; `emit-checklist.py` joins the two
when it writes a finding, and the store's own `affects` list names the
requirements a setting sits behind. `04-evidence-and-custody.md` covers what the
verification establishes.

## The logic for drafting a criterion

A benchmark requirement is prose about a system. A criterion is a condition about
a configuration file.

1. **Read the check text, not the fix text.** The check text states the condition
   under which the requirement is a finding. The fix text is remediation guidance
   for an administrator, and a revision touching only the fix text implies no
   rewrite.
2. **Draw the application-layer boundary.** What Splunk's own configuration can
   express becomes the criterion; the rest becomes `external:` lines. Do not
   invent an organization-defined value. Where the requirement turns on a list
   the organization owns, such as which indexes a role may search, test that the
   product can express the restriction and record in `external:` that the list is
   the assessor's comparison.
3. **Find the setting in the version-matched specification set.** The shipped
   `.conf.spec` files in `../splunk-spec-files-10.4.2` declare every setting, its
   default and its meaning. Cite it as `file:line` in `citation:`. A setting the
   specification set does not declare can still be assessed; `checks.tsv` marks
   it `undeclared`.
4. **Write one condition per line.** `02-how-it-decides.md` lists the operators
   and how a setting family resolves. Prefer a value test over an existence test
   on a family, unless one satisfied member genuinely satisfies the requirement.
   Reject two shapes:
   - Never passes: a stanza placeholder left in the key position, or a key with
     no default that a correct instance may omit. Open on every instance.
   - Never fails: a role stanza existence test, when the product ships nineteen
     of them in `etc/system/default`. Not a Finding on every instance.
5. **Where nothing governs it, say so.** Set `decidable: manual` and write
   `manual_reason:` stating what configuration can and cannot report. The
   requirement reports Not Reviewed, and the finding still carries the facts the
   assessment established. 35 of the 253 requirements are manual today.
6. **Set the confidence to what the criterion rests on.** A scaffold always
   writes `derived`; `criteria.json` has no field for anything higher, so raising
   it is a rule-file edit. 153 requirements are `derived`, 89 `documented`, 11
   `tested`.

### A worked example

`assess/rules/SRG-APP-000172-WSR-000104.rule`, CAT I: *the web server must
encrypt passwords during transmission.* The check text tells the assessor to
review the documentation and the deployed configuration and to raise a finding
where password transmission is not encrypted. It names no setting.

*Boundary.* Splunk Web is the product's own web interface, where people sign in
and search. It terminates TLS from its own configuration, so the application
carries this requirement. Three things it does not carry became `external:`
lines: a reverse proxy or load balancer that might terminate TLS and forward
credentials in the clear, whether the named certificate came from an approved
certificate authority, and password transmission onward to an LDAP or SAML
provider.

*Settings.* `web.conf` configures Splunk Web. `enableSplunkWebSSL` toggles
between HTTP and HTTPS and ships `false` (`web.conf.spec:70-73`). `serverCert`
and `privKeyPath` name the certificate and key, and both default to the
auto-generated pair the instance makes for itself (`:75-91`).

*Conditions.*

```
check:           web.conf [settings] enableSplunkWebSSL equals true
check:           web.conf [settings] serverCert non_empty
check:           web.conf [settings] privKeyPath non_empty
```

`equals true` rather than `present`, because the shipped default is `false`.
`non_empty` rather than a value, because the path is the site's own; whether the
certificate is approved is the `external:` line.

*A withdrawn condition.* A fourth was drafted: `enable_insecure_login equals
false`, guarding an alternate GET-based logon endpoint that carries the password
in a URL query string. Vendor verification returned the verdict
`finding_is_false`: the vendor's page states the endpoint exists only when the
setting is true, and the default is false. It sits in the file as a
`retired_check:` carrying the vendor's words.

*Confidence.* `documented`. Every setting the three live conditions test was
confirmed against the vendor's configuration-file reference, and the page is
cited in the finding.

## When an SRG is revised

Ten steps. Three need judgment.

1. **Swap the benchmarks.** Mechanical. New document into `benchmarks/`,
   superseded one out. `bin/extract-srg.py` concatenates every `.xml` in that
   directory without deduplicating, so two revisions in place duplicate every
   requirement in `srg-rules.json` and in the checklist. `bin/srg-diff.py` takes
   explicit paths.
2. **Diff the two revisions.** Running it is mechanical; reading it is judgment.

   ```
   bin/srg-diff.py --old /path/to/OLD-xccdf.xml --new benchmarks/NEW-xccdf.xml
   ```

   Read-only; there is no `--apply`. It reports added, withdrawn, changed and
   unchanged requirements, and for a changed one which part moved: the check
   text, the metadata (CCI, severity, group ID) or the narrative (title,
   discussion, fix text). It names the rule file behind each requirement and
   flags hand-written `vendor:`, `retired_check:`, `corrected:`,
   `manual_reason:` and `revised:` lines.
3. **Re-extract the inventory.** Mechanical. `bin/extract-srg.py` regenerates
   `srg-rules.json` and `srg-index.tsv`; `bin/map-cci.py` regenerates
   `cci-map.json`. Run the second whenever the first reports a CCI that was not
   there before. An unresolved CCI is a hard failure in that tool, not a blank
   row.
4. **Scaffold and refresh.** Mechanical. `assess/bin/build-rules.py` reports,
   `--apply` writes, and it never deletes a rule file. A requirement with a
   criterion and no file is **scaffolded**. An existing file's benchmark-owned
   fields are **refreshed** in place. A file whose criteria are customized and
   whose benchmark text has also moved is listed under `NEEDS READING` and left
   byte-identical. It scaffolds only what `criteria.json` carries, so step 5
   comes first.
5. **Write the criteria for the added requirements.** Judgment, by the six steps
   above. Add the determination to `sca-determinations.json` and the conditions
   to `criteria.json`, then re-run step 4. Or write the rule file by hand:
   `build-rules.py` reports a hand-written file as having no criterion rather
   than overwriting it.
6. **Re-read the changed requirements.** Judgment. Criteria written against the
   old check text may no longer assess what the requirement now asks. A changed
   fix text implies nothing. A changed severity or CCI was handled in step 4.
7. **Retire the orphans.** Judgment. `srg-diff.py` names a withdrawn
   requirement's rule file and removes nothing; that file may be the only place a
   retired check and its reason exist. Check whether the tool reported the
   requirement as re-identified, an SRG ID that changed while the V-number did
   not. That is a rename: move the file, and confirm the destination exists
   before removing the source.
8. **Regenerate the collection inventory.** Mechanical.

   ```
   assess/bin/derive-checks.py --merge           # report
   assess/bin/derive-checks.py --merge --apply   # write
   ```

   `--merge` keeps the rows already there and adds what the rules now need.
   Collection should be a superset of what the criteria decide on: a row no
   criterion uses still supplies the observed configuration a finding quotes.
9. **Re-collect on the instance.** Mechanical, and not optional after step 8. Run
   `assess/bin/assess.sh`. A criterion naming a setting collection never read
   fails silently, because a condition with no observation reads as "not
   present".
10. **Re-evaluate and re-emit.** Mechanical. Run `assess/bin/evaluate.sh`, then
    `assess/bin/emit-checklist.py`, with the arguments `00-START-HERE.md` gives.
    `evaluate.sh` exits 1 when any requirement is Open; that is the result, not a
    failed run.

### What a revision invalidates, and what it does not

| Change | Effect |
|---|---|
| a changed check text | The setting's vendor verification stands. What lapses is the claim that those conditions decide *this* requirement, which is why step 6 is a re-read |
| a new, unverified setting in a rewritten criterion | The whole requirement drops back to `derived`. Confidence is weakest-link |
| a product upgrade | `documented` and `tested` expire. Verification records the version it was confirmed against; re-verify against the version running |
| a withdrawn requirement | Nothing. Read its rule file before discarding it |

The verification store already holds a case where the shipped specification set
was a different version from the instance and every line citation in it was off.
No revision changes an observation: the evidence bundle from the previous run
still establishes what the instance held when it was read
(`04-evidence-and-custody.md`).

## A caution about earlier behavior

`build-rules.py` used to delete every file in `assess/rules/` and regenerate all
253 from `criteria.json` and `sca-determinations.json`. 57 requirements held
corrected operators or values that existed only in those files and were one run
from being erased; they have since been written back into `criteria.json`. The
generator no longer removes or rewrites a rule file. One residue: the 253
existing files still carry the superseded note "Regenerating overwrites it".
`build-rules.py` reports them under `note wording superseded`, and
`--refresh-header --apply` writes the current note in place and changes nothing
else.
