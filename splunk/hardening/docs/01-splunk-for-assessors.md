---
title: "Splunk for Assessors"
subtitle: "What the product is, in the terms this assessment uses"
author: "Security Control Assessment"
date: "2026-11-10"
---

# Splunk for Assessors

You do not need to know Splunk to read an assessment of it. This explains the parts the
findings refer to.

## What Splunk is

Splunk collects machine data - logs, events, metrics - from many systems, stores it, and
lets people search it. In an accreditation it is usually the central log server: the
place audit records go to be kept, protected and reviewed.

Two benchmarks govern it: the Central Log Server SRG, because it is a **log server**, and
the Web Server SRG, because it serves a **web interface**.

## The parts

A Splunk deployment is built from three roles. One machine can hold more than one.

| Role | What it does |
|---|---|
| **Forwarder** | Sits on a machine you want logs from. Reads them, sends them on. Stores nothing. |
| **Indexer** | Receives data, writes it to disk, answers searches. The audit records live here. |
| **Search head** | The web interface. People sign in here, run searches and read dashboards. |

Data moves one way: forwarder, then indexer, then whoever searches it.

The role decides which requirements apply. A forwarder stores nothing, so requirements
about protecting stored audit records land on an indexer and not on it. The assessment
reads the role from the configuration.

## How Splunk is configured

Settings live in plain text files ending `.conf`. A file holds **stanzas** in square
brackets, and each stanza holds **keys** with values:

```
[sslConfig]
sslVersions = tls1.2
serverCert = /opt/splunk/etc/auth/server.pem
```

A finding writes that as `server.conf [sslConfig] sslVersions`: the file, the stanza, the
key.

## Layering

The same setting can appear in several files at once. Splunk merges them, and one value
wins. From weakest to strongest:

1. **`etc/system/default`** - what Splunk ships.
2. **An app** - a bundle of configuration added to the instance. Most deliberate
   configuration arrives this way.
3. **`etc/system/local`** - the instance's own local settings. **Beats every app.**

A setting present in an app is not necessarily in effect: if `etc/system/local` sets the
same key, the local value wins. So every finding names the file the winning value came
from, and which of the three layers that file belongs to.

## How the assessment reads all this

Splunk ships a command called `btool`. It prints the merged value actually in effect and,
asked for it, the file that value came from. The assessment is built on it. Two
properties make it suitable:

- **It needs no password.** An assessment needs no credentials on the system it assesses.
- **It only reads.** It cannot change a setting.

One caution for anyone verifying by hand: `btool check` reports invalid settings, but it
exits successfully even when it has found problems. Read its output, not its exit status.
This assessment reads the output.

## Vocabulary you will meet in findings

| Term | Meaning |
|---|---|
| **conf file** | a configuration file, for example `web.conf` |
| **stanza** | a named section inside it, written `[sslConfig]` |
| **key** | one setting inside a stanza |
| **app** | a bundle of configuration added to an instance |
| **`etc/system/local`** | the instance's own settings, which beat every app |
| **`etc/system/default`** | the shipped settings, which lose to everything |
| **forwarder, indexer, search head** | the three roles above |
| **`btool`** | the command that shows what is actually in effect, and from which file |
