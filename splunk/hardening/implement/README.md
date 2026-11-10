# Implementation module

**Paused. Nothing here is built.** The assessment module is being completed first.

## The design, written

| Document | Covers |
|---|---|
| `CHECKPOINT-DESIGN.md` | the snapshot and rollback: what is captured, and why restore works offline |
| `APPLY-DESIGN.md` | how a change is written, proven, batched and refused |
| `../docs/RISK-MODEL.md` | how risk is measured per instance, and what a referral must contain |

Read them in that order. Nothing may change an instance until the checkpoint mechanism
exists and has been proven restorable.

## What this will be

Applying hardening changes to a Splunk instance, and proving they took. Deliberately
separate from assessment: deciding what is true and deciding what to alter are different
problems, and getting the second one wrong takes a system down.

Planned shape, so it is not re-derived:

- **Changes are applied by writing configuration files**, validated with `btool check`,
  then reloaded or restarted. Not through the REST interface: that needs a cached session
  token which is absent on a forwarder, and the assessment module's whole value is that it
  needs no credentials.
- **Applied means `btool` confirms it**, naming our file as the winner. A write that
  succeeded but was outranked by `etc/system/local` is not applied, whatever its exit code
  said.
- **Risk is measured per instance, not read from a table.** The same change is routine on
  one instance and an outage on another. See `../docs/RISK-MODEL.md`, which is written and
  records the ten signals, the six conditions that make the tool refuse, and what a
  referral must contain.
- **Batches are tracked units** so rollback is per batch, ordered by least availability
  risk rather than by severity. Strict CAT I first is wrong: that set holds FIPS, which
  cannot be changed on an installed instance, transport changes that sever forwarders, and
  authentication changes that lock the operator out.
- **A checkpoint before anything**, restorable without authenticating and with splunkd
  stopped, because the failure it exists for may be exactly that.

## What it shares with assessment

`../lib` holds what both use. Assessment reads; implementation reads and writes. Anything
that decides what is true belongs in assessment and is used here, not reimplemented.

## Before starting

Four things must be proven before this module is trusted, and none is done: a checkpoint
that is provably restorable, a restore that works with splunkd stopped and without
authenticating, apply being safe to repeat, and the health gate catching a real break.

That last one must not be skipped. A gate that has never seen a failure is unproven, and
proving it means deliberately severing something and requiring the rollback to fire.
