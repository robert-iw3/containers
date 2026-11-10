---
title: "Checkpoint and Rollback"
subtitle: "Splunk hardening - implementation module design"
author: "Security Control Assessment"
date: "2026-11-10"
---

# Checkpoint and Rollback

**Planned, not built.** This is the mechanism the rest of the implementation module
depends on. Nothing may change an instance until a checkpoint of it can be taken and
proven restorable, because a change you cannot undo is not a change, it is a commitment.

Measurements here were taken on a running Splunk 10.4.2 instance on 2026-11-10.

## What a checkpoint contains

The configuration surface that can change is small. The installation is not.

| Path | Size | Files | Why |
|---|---|---|---|
| `etc/system/local` | 52 KB | 9 | the instance's own settings, which outrank every app |
| `etc/apps/*/local` | 48 KB | 7 | per-app overrides, where a hardening app writes |
| `etc/auth` | 180 KB | 25 | certificates, keys, and `splunk.secret` |
| `etc/passwd` | 4 KB | 1 | local accounts |
| `etc/users` | 40 KB | 5 | per-user settings |
| `etc/licenses` | 12 KB | 1 | licensing |
| **Total captured** | **~336 KB** | | |
| `etc` in full, for contrast | 1.2 GB | | |

**`etc/apps/*/default` is excluded, and that is the whole difference.** It is shipped
content: 1.2 GB of it, which does not change and which a restore must not touch. Capturing
it would make a checkpoint three thousand times larger for no recoverable state.

A checkpoint is therefore fast enough to take before every batch, which is the only
cadence that makes rollback meaningful.

## What must be captured and restored together

**`etc/auth/splunk.secret` and every file holding a value it encrypted.** On the reference
instance, `$7$` values appear in three places at once: `system/local/web.conf`,
`system/local/server.conf` and `system/local/passwords.conf`. Restoring the key without
those files, or those files without the key, leaves every stored credential undecryptable:
the TLS private key passphrase, stored passwords, bind credentials.

They are one unit in both directions. A checkpoint that captures part of it is not a
checkpoint.

`etc/passwd` is the exception and is worth knowing: local accounts are SHA512-crypt and
self-contained, so they survive a `splunk.secret` mismatch. That is the property the
recovery path below rests on.

## Ownership and mode are part of the data

`splunk.secret` is mode `0400` owned by the service account. Files under `etc/` owned by
the wrong account stop splunkd from starting - measured on this platform, and the reason
the assessment module refuses to run as the wrong user.

A restore that puts the right bytes back with the wrong ownership creates the outage it
was meant to undo. Ownership and mode are captured per file and restored with the content.

## Restore must work in the situation it exists for

The failure a rollback answers is usually one of two, and both break the obvious approach:

- **The operator cannot authenticate.** An authorization change took effect and locked
  them out. So restore cannot require a login.
- **splunkd will not start.** A configuration change stopped it. So restore cannot require
  a running instance.

Restore is therefore **file-level and offline**: replace files, fix ownership, start. It
never calls the management interface. The tools it needs are auth-free and work with
splunkd stopped, which was measured: `btool` reads configuration without credentials or a
running instance, `splunk hash-passwd` needs no session, and the user subcommands are
tagged offline-capable.

## The hazard: splunkd rewrites its own configuration

splunkd was observed rewriting `etc/system/local/web.conf` seconds after starting. Two
consequences:

- A checkpoint taken while splunkd is running can capture a file mid-rewrite.
- A file restored under a running splunkd can be overwritten by it.

So a restore stops splunkd first, replaces files, then starts it. A checkpoint taken while
running is still useful and is what a pre-batch snapshot will be, but the manifest records
that splunkd was running when it was taken, so a reader knows which kind they have.

## Verifying a checkpoint without restoring it

A backup nobody has restored is a hope. But verifying by restoring destroys the state you
were protecting, so verification has to be non-destructive:

- every captured file has a SHA-256 in the manifest, recomputable in place;
- the manifest records the expected file count and total size per captured path, so a
  truncated capture is visible;
- a restore can be run in dry-run, listing exactly which files it would replace, create or
  remove, and with what ownership, without touching anything;
- the restore path itself is exercised against a disposable instance, not against the one
  being protected.

## Rollback on error

Every apply is a tracked batch, and rollback is per batch so a bad batch comes out without
disturbing good ones.

The sequence, with the gate that makes it automatic:

1. Health check. **If the instance is not healthy, stop.** A change applied to an already
   degraded instance cannot be attributed, and compounds a fault already there.
2. Checkpoint, verified.
3. Apply the batch.
4. Health check again, compared against the **baseline values**, not a threshold. Three
   forwarders connected before and two after is a regression even though two exceeds zero.
5. On regression: restore the checkpoint, confirm health returns to baseline, and report
   what the change did.

Step 5 is the part that must be proven before this module is trusted, and proving it means
deliberately breaking something: sever the link between two tiers, require the health check
to detect it by comparison, require the rollback to fire, require health to return. A gate
that has never seen a failure is unproven.

## What a checkpoint cannot undo

Stated plainly, because a rollback that is believed to cover more than it does is worse
than none:

- **Install-time settings.** FIPS mode is chosen at installation. No file restore reaches
  it; the remedy is a rebuilt instance.
- **Indexed data.** A checkpoint holds configuration, not the index. A change that deleted
  or re-routed data is not undone by restoring configuration.
- **Changes on another host.** A transport change needs both ends altered together, and a
  checkpoint covers the instance it was taken on. The peer needs its own.
- **Anything already forwarded.** Data that left the instance is gone from this instance's
  control.
