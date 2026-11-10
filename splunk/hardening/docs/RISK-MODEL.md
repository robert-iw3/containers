---
title: "Implementation Risk Determination"
subtitle: "Splunk Enterprise application configuration hardening"
author: "Security Control Assessment"
date: "2026-11-10"
---

<!-- Generated-adjacent design record. Measurements in it were taken on 2026-11-10. -->
\newpage

## Document Control

| Field | Value |
|---|---|
| Document title | Implementation Risk Determination |
| System | Splunk Enterprise 10.4.2, application configuration |
| Version | 1.0 |
| Date | 2026-11-10 |
| Classification | Unclassified |

**Purpose.** States how the hardening tool decides, for a specific instance, whether a
configuration change may be applied automatically or must be referred for manual
implementation; what it measures to reach that decision; and what a referral must contain.

**Audience.** Information System Security Officer, Information System Security Manager,
Security Control Assessor, and the administrator who implements a referral.

## The principle

A change is automated only when the instance itself shows it to be safe. Risk is not read
from a table of settings: the same change is routine on one instance and an outage on
another, and the difference is measurable. Where a measurement shows the change could
interrupt service or remove access, the tool does not attempt it. It produces a referral
that states what to do, why it was not automated, and what must be true first.

Refusing to automate is a result, not a failure. A tool that applies a change it cannot
assess the consequences of has moved the risk from the change to the tool.

## What is measured, and how

Every signal below is read without credentials and without writing to the instance. Each was
confirmed obtainable on a running Splunk 10.4.2 instance on 2026-11-10, across an indexer, a
heavy forwarder and a universal forwarder.

| Signal | Source | What it bounds |
|---|---|---|
| Connected forwarders | distinct `guid` in `metrics.log` | blast radius of a transport or TLS change |
| Search peers | `btool distsearch list --debug`, `servers =` | blast radius of a distributed change |
| Cluster mode | `btool server list clustering`, `mode` | whether a restart is local or rolling |
| Ingest rate | `metrics.log` `group=thruput`, `kbps` | the cost of an ingestion gap |
| Blocked queues | `metrics.log` `blocked=true` | whether the instance is already backed up |
| Authentication method | `btool authentication list`, `authType` | exposure to loss of access |
| Local accounts | lines in `etc/passwd` | whether a way back in exists |
| Winning configuration layer | `btool <conf> list --debug` | whether a write can take effect at all |
| Reload behavior | `reload.<conf>` in the shipped `app.conf` | whether applying interrupts service |
| Recent error rate | `splunkd.log` | whether the instance is already unhealthy |

**Count forwarders by identity, not by log line.** On the reference indexer the
`tcpin_connections` line count was 340 while the distinct forwarder count was 2. A rule keyed
on the line count would read a two-forwarder instance as a two-hundred-forwarder one.

**Reload behavior is published by the product, not inferred.** Splunk 10.4.2 ships a
per-configuration reload table in the default `app.conf`, read with
`btool app list --debug`. Its values are `never`, meaning the file is not reloadable and a
restart is required; `http_post`, meaning a reload is triggered by a POST, as for `web` and
`server`; `access_endpoints`, meaning a live reload handler exists; and `simple`, meaning the
configuration layer is re-read with no handler. A configuration absent from the table has no
reload handler, which is treated as requiring a restart. Eighty-nine entries were present on
the reference indexer.

## The determination

A change is **referred for manual implementation**, and not attempted, when any of the
following holds on the instance being assessed.

Each condition below is stated with the reason it bars automation.

**The setting is established at installation.** It cannot be changed on an installed
instance at all. FIPS mode is the known case, and the remedy is an instance installed with
the setting in place rather than a configuration change.

**The winning layer is `etc/system/local`.** That layer outranks every app, so a write the
tool makes cannot take effect. Applying it and reporting success would be false, and on the
reference indexer 76 of 1,222 observed settings were supplied from that layer.

**The change affects authentication or authorization, and one or fewer local accounts
exist.** `reload.authentication` and `reload.authorize` are both `access_endpoints`, so such a
change takes effect on reload with no restart and no interval in which to notice a mistake.
With a single local account there is exactly one route back in.

**The change affects transport or certificates while forwarders are connected.** Both ends
must change together; changing one severs the connection and data stops.

**A restart is required and the instance is a cluster member.** The restart becomes a rolling
operation across peers, which needs orchestration this tool does not perform.

**The instance is already degraded.** A change applied to an unhealthy instance cannot be
attributed to its own effect, and it compounds a fault already present.

Where none of these holds, the change is applied, and the restart or reload the product
requires for it is stated before it is attempted.

## What a referral contains

A referral is the output when the tool declines to act. It names the measurements that
produced the decision, so the reader can disagree with it on the evidence.

- **What.** The configuration file, stanza, key and the value the requirement calls for.
- **Why not automated.** The conditions above that were met, with the measured values that
  met them. Not a severity label: the numbers.
- **When it becomes safe.** The conditions under which the obstacle is removed, for example
  a maintenance window with both tiers changed together, or a verified second administrative
  account.
- **Where.** The absolute path of the file to edit and every instance affected, including
  instances other than the one assessed where a coordinated change is required.
- **How.** The vendor's documented procedure.
- **Dependencies.** Everything that must exist or be true first, each one checkable.

### Citing vendor guidance

A referral sends a person to the vendor's own documentation, whether or not the assessed
instance can reach a network. Three sources are cited, in this order:

1. **The configuration specification shipped with the product**, by file and line. This is
   vendor documentation present on every instance, and it is the authoritative statement of a
   setting's meaning, permitted values, default and restart behavior.
2. **The vendor documentation topic**, by URL where the specification file supplies one.
   Fifty-nine of the shipped specification files carry a `docs.splunk.com` reference, and
   `indexes.conf` carries the topic on determining whether a restart is required.
3. **The benchmark's own fix text**, from the governing Security Requirements Guide or the
   product Security Technical Implementation Guide, which states what the requirement asks
   for in the authority's words.

A URL is never constructed. Where no reference is published on the instance for a setting,
the referral names the documentation subject the reader needs and records that the link is to
be confirmed for the installed version, rather than presenting an invented path as a citation.
