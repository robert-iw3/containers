---
title: "Splunk Hardening Toolkit"
subtitle: "How it decides"
author: "Security Control Assessment"
date: "2026-11-09"
---

# How It Decides

This document states how each status is reached.

## The boundary: the application only

Splunk Enterprise is an application that runs on an operating system. This
assessment reads **Splunk's own configuration and nothing else**. No operating
system setting is read, changed, or judged.

Many requirements in the governing baselines describe a whole system: a log
server, its host, its network, and the people who run it. Where a requirement
reaches past Splunk's configuration, the part Splunk controls is assessed. The
finding names the rest as an external dependency, left for someone else to
answer.

## The four statuses

| Status | Means |
|---|---|
| **Not a Finding** | Every condition of the criterion was met by the configuration observed. |
| **Open** | At least one condition was not met. The finding names the setting and the file. |
| **Not Reviewed** | No criterion could be applied. The reason is recorded. |
| **Not Applicable** | Reserved. Nothing currently produces it. |

`Not Applicable` is unused. Declaring a requirement inapplicable is a
determination that needs its own evidence.

## A criterion

A criterion is one or more conditions. Each condition names a configuration file,
a stanza (a bracketed section in that file), a setting, an operator, and, where
the operator needs one, a value:

```
check:  web.conf [settings] enableSplunkWebSSL in 1|true
check:  server.conf [sslConfig] sslVersions not_matches (^|,)\s*(ssl3|tls1\.0)\s*(,|$)
```

The operators are fixed: `present`, `absent`, `non_empty`, `equals`,
`not_equals`, `in`, `not_in`, `matches`, `not_matches`, `min`, `max`.

One condition per line. There is no `AND` operator. A requirement needing two
conditions gets two lines, and **all** lines must pass for Not a Finding.

Each requirement is one file in `assess/rules/`, named for the requirement. To
change how something is assessed, edit that file; it is read at run time.

## Families of settings

Baselines and vendor specifications both describe a family of settings with a
placeholder in angle brackets:

| Placeholder | Family |
|---|---|
| `[role_<roleName>]` | every role stanza |
| `[tcpout:<group>]` | every forwarding group |
| `SEDCMD-<class>` | every setting whose name begins `SEDCMD-` |

Matched literally, none of these exists, so such a criterion could never pass.
Placeholders are resolved against the settings the instance actually has:

- an **existence** test (`present`, `absent`, `non_empty`) passes if **any** real
  setting in the family satisfies it;
- a **value** test must hold for **every** one. One stanza left at a weak value
  is still an exposure.

A placeholder also matches the unnamed default stanza, and the separator before
it is optional. This follows Splunk's own inheritance: a value set in `[tcpout]`
supplies the default for every `[tcpout:group]`, so a criterion on
`[tcpout:<group>]` is satisfied by `[tcpout]`.

## What a status rests on: confidence

Two requirements can both be Open without being equally trustworthy. Each
criterion carries a confidence, stated in words in the checklist:

| Confidence | Means |
|---|---|
| **derived** | The criterion was built from the benchmark check text and the configuration specification shipped with the product. It has not been confirmed against the vendor's published documentation. Treat it as a first reading. |
| **documented** | Every setting the criterion tests was confirmed against the vendor's published documentation, and the page is cited in the finding. |
| **tested** | As above, and the behavior was exercised on a running instance - the value was applied and the product accepted or rejected it. |

Confidence is the **weakest link**. A requirement is recorded `documented` only
when every setting it tests was confirmed. One unconfirmed setting holds the
whole requirement at `derived`.

The specification shipped with the product has been found to disagree with the
vendor's documentation, and both with the running product. Reviewing a criterion
against the document it was written from catches only internal inconsistency.

## Withdrawn criteria

Where the vendor's documentation contradicted a criterion outright, the criterion
is **withdrawn rather than deleted**. The finding lists it under
`CRITERIA WITHDRAWN AFTER VERIFICATION` with the reason.

A withdrawal is not applied if it would leave a requirement with no criterion at
all, because a requirement with none evaluates to Not Reviewed. Those cases are
reported for reading.

## Why something is Not Reviewed

One reason remains in the current run: **the criterion cannot be decided from
configuration**. The objective of these requirements is a procedure, a person, or
an organizational artifact: who the ISSO is, whether an agreement exists, what
the site considers an attack.

Where the assessment can still contribute, the finding reports the facts it
established: the version running, the accounts that exist, the state observed.

## What it never does

**It does not change anything.** Every observation comes from `splunk btool`, the
Splunk command that prints the configuration in effect and writes nothing. No
code path in the assessment modifies an instance, so it can run on a production
system without a change request.

**It does not report a requirement satisfied because nobody assessed it.** A
requirement nobody assessed is Not Reviewed, with the reason recorded.
