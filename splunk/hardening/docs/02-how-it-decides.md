---
title: "Splunk Hardening Toolkit"
subtitle: "How it decides"
author: "Security Control Assessment"
date: "2026-11-09"
---

# How It Decides

A checklist is only worth what its determinations rest on. This document states
exactly how each status is reached, so a reviewer can disagree with a specific
step rather than with the result as a whole.

## The boundary: the application only

Splunk Enterprise is an application running on an operating system. This
assessment reads **Splunk's own configuration and nothing else**. No operating
system setting is read, changed, or judged.

That is a deliberate limit, not an oversight. Many requirements in the governing
baselines describe a whole system: a log server, its host, its network, and the
people who run it. Judging Splunk against the whole text would fail the
application for things it has no setting to control.

So where a requirement reaches past what Splunk can configure, the part Splunk
*does* control is assessed and the rest is **named in the finding** as an
external dependency. It is not counted against the application, and it is not
quietly dropped either - an assessor reading the finding sees what remains for
someone else to answer.

## The four statuses

| Status | Means |
|---|---|
| **Not a Finding** | Every condition of the criterion was met by the configuration observed. |
| **Open** | At least one condition was not met. The finding names the setting and the file. |
| **Not Reviewed** | No criterion could be applied. The reason is recorded. |
| **Not Applicable** | Reserved. Nothing currently produces it. |

`Not Applicable` is deliberately unused. Declaring a requirement inapplicable is
a determination that needs its own evidence, and inventing one to reduce a count
is the failure a checklist exists to prevent.

## A criterion

A criterion is one or more conditions. Each condition names a configuration file,
a stanza, a setting, an operator, and where the operator needs one, a value:

```
check:  web.conf [settings] enableSplunkWebSSL in 1|true
check:  server.conf [sslConfig] sslVersions not_matches (^|,)\s*(ssl3|tls1\.0)\s*(,|$)
```

The operators are fixed: `present`, `absent`, `non_empty`, `equals`,
`not_equals`, `in`, `not_in`, `matches`, `not_matches`, `min`, `max`. One
condition per line. There is no `AND` operator - a requirement needing two
conditions gets two lines, and **all** lines must pass for Not a Finding.

Each requirement is one file in `assess/rules/`, named for the requirement. To
change how something is assessed, edit that file; it is read at run time.

## Families of settings

Baselines and vendor specifications both describe a family of settings with a
placeholder in angle brackets:

- `[role_<roleName>]` - every role stanza
- `[tcpout:<group>]` - every forwarding group
- `SEDCMD-<class>` - every setting whose name begins `SEDCMD-`

Matched literally, none of these can ever exist, so a criterion written that way
could never pass on any instance. They are resolved against what the instance
actually has, on this reading:

- an **existence** test (`present`, `absent`, `non_empty`) passes if **any** real
  setting in the family satisfies it;
- a **value** test must hold for **every** one, because a single stanza left at a
  weak value is the exposure the requirement is about.

A placeholder also matches the unnamed default stanza, and the separator before
it is optional. This is Splunk's own inheritance: a value set in `[tcpout]`
supplies the default for every `[tcpout:group]`, so a criterion on
`[tcpout:<group>]` is satisfied by `[tcpout]`. Requiring a named stanza would
report a finding against configuration that does govern the listener.

## What a status rests on: the confidence ladder

Two requirements can both be Open and not be equally trustworthy. Each carries a
confidence, and the checklist states it in words:

| Confidence | Means |
|---|---|
| **derived** | The criterion was built from the benchmark check text and the configuration specification shipped with the product. It has not been confirmed against the vendor's published documentation. Treat it as a first reading. |
| **documented** | Every setting the criterion tests was confirmed against the vendor's published documentation, and the page is cited in the finding. |
| **tested** | As above, and the behavior was exercised on a running instance - the value was applied and the product accepted or rejected it. |

Confidence is the **weakest link**. A requirement is recorded `documented` only
when *every* setting it tests was confirmed. One unconfirmed setting holds the
whole requirement at `derived`, because that is exactly where it can be wrong.

This matters because the specification shipped with the product has been found to
disagree with the vendor's own documentation, and both have been found to
disagree with the running product. Reviewing a criterion against the same
document it was written from catches internal inconsistency and nothing else.

## Withdrawn criteria

Where the vendor's documentation contradicted a criterion outright, the criterion
is **withdrawn rather than deleted**. The finding lists it under
`CRITERIA WITHDRAWN AFTER VERIFICATION` with the reason, so the record shows what
was considered and why the test was dropped.

A withdrawal is never applied if it would leave a requirement with no criterion
at all. A requirement with none evaluates to Not Reviewed, and trading a wrong
answer for no answer is not an improvement. Those cases are reported for reading.

## Why something is Not Reviewed

Only one reason remains in the current run: **the criterion cannot be decided
from configuration**. These are requirements whose objective is a procedure, a
person, or an organizational artifact - who the ISSO is, whether an agreement
exists, what the site considers an attack. Configuration cannot answer them, and
a tool that claimed otherwise would be guessing.

Where the assessment can still contribute, the finding reports the facts it
established - the version running, the accounts that exist, the state observed -
so whoever answers the requirement is not starting from nothing.

## What it never does

**It does not change anything.** Every observation comes from `splunk btool`,
which reads configuration and writes none. There is no code path in the
assessment that modifies an instance, so it can run on a production system
without a change request.

**It does not report a requirement satisfied because nobody assessed it.** An
unassessed requirement is Not Reviewed, with the reason recorded.
