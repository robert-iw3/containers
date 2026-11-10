---
title: "Applying a Change"
subtitle: "Splunk hardening - implementation module design"
author: "Security Control Assessment"
date: "2026-11-10"
---

# Applying a Change

**Planned, not built.** How a hardening change is made, proven, and undone. Read
`CHECKPOINT-DESIGN.md` first: nothing here may run without a verified checkpoint.

## The command surface

The commands are the operator's questions, in the order they ask them.

| Command | The question |
|---|---|
| `plan` | What would you change, and what would it disturb? |
| `apply --batch ID --confirm` | Do it. Refuses without `--confirm`. |
| `verify` | Did it take? |
| `status` | What is applied, what is left? |
| `rollback ID` | Undo that batch. |

**Nothing changes without `--confirm`.** `plan` is the default because a tool that
modifies on bare invocation will eventually be invoked bare.

## How a change is written

**By writing the configuration file.** Not through the management interface. That path
needs an authenticated session, and the token is per-user, per-host and per-port: the same
call that worked on an indexer failed on a forwarder with "Authentication needed". An
implementation tool that cannot run on a forwarder is not one.

File writes need no credentials, work on every role, and are what a rollback replaces.

Each change is then:

1. Written to the target file.
2. Validated with `btool check`. **Its output is the result; its exit status is not** - it
   exits successfully while reporting invalid settings. Parse the output.
3. Reloaded or restarted according to what the product says is required.
4. Confirmed by reading it back.

## Reload or restart is read from the product, not assumed

Splunk publishes the answer. The shipped `app.conf` carries a per-configuration reload
table, read with `btool app list --debug` - 89 entries on the reference indexer.

| Value | Meaning |
|---|---|
| `never` | not reloadable; a restart is required |
| `http_post` | reload triggered by a POST, as for `web` and `server` |
| `access_endpoints` | a live reload handler exists |
| `simple` | the configuration layer is re-read, no handler |

A configuration absent from the table has no handler and is treated as requiring a
restart. Nothing here hardcodes a restart list.

One measured caution: a reload call returns success even for a configuration file that has
no reload handler at all. A reload's status is never evidence that anything was applied.

## Applied means btool confirms it

A write that returned success is not a change. After every apply the setting is read back
with `btool --debug`, and both must hold:

- the value is what was written, and
- **the file that supplied it is ours**.

A value outranked by `etc/system/local` reports as **not applied**, with the winning file
named. On the reference indexer 76 of 1,222 observed settings came from that layer, so
this is not a corner case. Reporting those as applied would be the tool lying about the
thing it exists to do.

This is also why the implementation module cannot grade its own work. The proof is a fresh
assessment run by the assessment module, reading the instance with no knowledge of what
was attempted.

## Batching, and why severity is the wrong order

A batch is a tracked unit so rollback is per batch. Batches are ordered by **least
availability risk first**, not by severity.

Strict CAT I first is wrong on measured grounds. That set contains FIPS, which cannot be
changed on an installed instance at all; transport and certificate changes, which sever
every connected forwarder unless both ends change together; and organization-level
authentication, which can lock the operator out of the instance they are hardening.

The order:

| Pass | Contains | Coordination |
|---|---|---|
| 1 | takes effect on reload, or needs a restart | none, or a brief predictable outage |
| 2 | transport and certificates | both ends, together |
| 3 | authentication and authorization | a verified second account first |
| 4 | install-time settings | a rebuilt instance; not an apply |

Severity orders requirements **within** a pass, never across them.

Selection is by requirement, by severity, by impact, or by a named batch, so an operator
can take the safe slice of a severity rather than all of it.

## Applying is safe to repeat

Re-running an apply changes nothing the second time. An interrupted run is therefore safe
to re-run, which is the only way a batch is recoverable without reasoning about how far it
got.

## When the tool refuses

Risk is measured per instance, not read from a table - see `../docs/RISK-MODEL.md` for the
ten signals and the six conditions. Where a condition holds, the tool does not attempt the
change. It produces a **referral**: what to do, why it was not automated with the measured
values that decided it, when it becomes safe, where including every other instance
affected, how per the vendor's documented procedure, and the dependencies that must exist
first.

Refusing is a result. A tool that applies a change whose consequences it cannot assess has
moved the risk from the change to the tool.

## The loop an operator actually runs

```
health-check            # must pass, or stop
plan --impact none      # what is safe, and what it touches
apply --batch ID --confirm
health-check            # compared against baseline values
  pass -> assess, and keep the evidence
  fail -> rollback ID automatically, confirm health returns
```

Then the next pass, once the instance has run long enough to trust.

## What it shares with assessment

`../lib` holds what both use: target discovery and the guard that refuses to run as the
wrong account. Anything that decides what is true belongs to the assessment module and is
called, not reimplemented. Two implementations of "is this setting in effect" would
eventually disagree, and the one that disagreed silently would be this one.
