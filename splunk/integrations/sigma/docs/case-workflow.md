# Working a detection: notes, evidence, and a resolution

Sigma rules produce false positives. That is not a defect in them — a rule
describes a behaviour, and legitimate software exhibits attacker-like
behaviour all the time. A detection product that cannot record "we looked
at this and it was the backup agent" makes an analyst look at it again next
week, and the week after.

This is the record of that decision.

---

## The shape of it

Every action is its own event in the `sigma_cases` index. Opening a case,
adding a note, attaching evidence and resolving it are four separate
entries. The current state of a case is derived by taking the latest value
of each field; the entries behind it stay readable as a history.

Nothing is ever overwritten. Correcting something means adding the
correction, and both remain. For a DFIR team that is the point: who decided
what, when, and on what basis is the part that has to survive, and it is
exactly the part that an editable lookup loses.

| Entry | Written when | Carries |
|---|---|---|
| `open` | a case is started on a detection | the rule, host, detection time, severity |
| `note` | an analyst records what they found | free text, their name, the time |
| `evidence` | something worth keeping is attached | free text — a search, an event id, a hash |
| `resolve` | the case is closed | the resolution and the reason |

Resolutions are deliberately few:

- **false positive** — the activity was legitimate
- **true positive** — this was real
- **benign expected** — known and accepted in this environment
- **duplicate** — the same activity as another case
- **inconclusive** — could not be determined

`inconclusive` exists because "we could not tell" is a real outcome and
forcing it into one of the others corrupts every number derived from them.

---

## The case id

A case id is derived from the detection it concerns:

    md5(rule_id | host | detection time), first 12 characters

Opening a case twice on the same detection therefore lands on the same
case rather than creating a second one, and no sequence counter has to be
kept anywhere. A detection with no entries in `sigma_cases` is untriaged,
which is what the "Detections with no case yet" figure counts.

---

## One setting the operator has to make

Writing a case entry uses `collect`, which Splunk classifies as a risky
command and **blocks from dashboards by default**. That default is
correct: a dashboard that can write to an index is a dashboard that can be
made to write to an index.

Case Work will therefore do nothing until an operator decides otherwise.
In `$SPLUNK_HOME/etc/system/local/web.conf`:

```ini
[settings]
enable_risky_command_check_dashboard = false
```

and restart splunkd. This is instance-wide, so it is a decision about the
whole installation rather than about this app, which is why the app does
not ship it. Read it before enabling it.

If you would rather not, the alternative is to leave Case Work read-only
and record decisions in `lookups/sigma_allowlist.csv` by hand. That
suppresses future detections but keeps no history of why, which is the
trade being made.

---

## Tuning is what the record is for

A single false positive is triage. The same rule called a false positive
two or three times is a tuning job nobody has done, and it is costing an
analyst every time it fires.

The "Rules repeatedly resolved as false positive" panel reads the case
record and names them, with the rule id ready to paste into
`lookups/sigma_allowlist.csv`:

| Column | Meaning |
|---|---|
| `sigma_rule_id` | the rule to allowlist, or blank for every rule |
| `sigma_src_host` | the host, or blank for every host |
| `reason`, `added_by`, `added_on` | why, who and when, so it can be reviewed later |

The `sigma_detections` macro applies the allowlist, and every dashboard
reads through that macro, so an entry takes effect everywhere at once.

Allowlist rather than disable. A disabled rule is invisible; an allowlisted
one still records what it caught, and the entry says who decided to stop
looking at it and why.

---

## What this is not

It is not a ticketing system and does not try to be. There is no
assignment, no SLA, no escalation path and no integration with whatever
tracks work in your organisation. It records the security decision — what
was found and how it ended — and leaves the workflow around that to the
system that already owns it.

If cases here need to reach that system, the `sigma_cases` index is an
ordinary Splunk index: a scheduled search with a webhook action will carry
them out, and that is a smaller thing to build than a second ticket queue
nobody reconciles.
