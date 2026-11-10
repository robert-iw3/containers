---
title: "Splunk for Assessors"
subtitle: "What the product is, in the terms this assessment uses"
author: "Security Control Assessment"
date: "2026-11-10"
---

# Splunk for Assessors

You do not need to know Splunk to read an assessment of it. This explains the parts the
findings refer to. It is short on purpose.

## What Splunk is

Splunk collects machine data - logs, events, metrics - from many systems, stores it, and
lets people search it. In an accreditation it is usually the central log server: the
place audit records go so they can be kept, protected and reviewed.

That role is why two benchmarks govern it. It is a **log server**, so the Central Log
Server SRG applies. It also serves a **web interface** to its users, so the Web Server
SRG applies as well.

## The parts

A Splunk deployment is built from three roles. One machine can hold more than one.

| Role | What it does |
|---|---|
| **Forwarder** | Sits on a machine you want logs from. Reads them, sends them on. Stores nothing. |
| **Indexer** | Receives data, writes it to disk, answers searches. The audit records live here. |
| **Search head** | The web interface. People sign in here, run searches and read dashboards. |

Data moves one way: forwarder, then indexer, then whoever searches it.

Which role a machine has decides which requirements bite. A forwarder stores nothing, so
requirements about protecting stored audit records do not land on it the way they land on
an indexer. The assessment reads the role from the configuration rather than being told.

## How Splunk is configured

Settings live in plain text files ending `.conf`. A file holds **stanzas** in square
brackets, and each stanza holds **keys** with values:

```
[sslConfig]
sslVersions = tls1.2
serverCert = /opt/splunk/etc/auth/server.pem
```

A finding writes that as `server.conf [sslConfig] sslVersions` - the file, the stanza,
the key. That is all those three words mean.

## The part that matters most: layering

The same setting can appear in several files at once. Splunk merges them, and one wins.
From weakest to strongest:

1. **`etc/system/default`** - what Splunk ships. Nobody edited it.
2. **An app** - a bundle of configuration added to the instance. Most deliberate
   configuration arrives this way.
3. **`etc/system/local`** - the instance's own local settings. **Beats every app.**

This decides whether a finding is true. A setting present in an app is not necessarily
in effect: if `etc/system/local` sets the same key, the local value wins and the app's is
ignored. A tool that reported the app's value would claim a control that is not there.

So every finding names the file the winning value came from, and which of the three
layers that file belongs to. When a value comes from `etc/system/local`, the finding says
so, because no app can override it.

## How the assessment reads all this

Splunk ships a command called `btool` that prints the merged result - the value actually
in effect - and, asked for it, the file each value came from. That is the whole basis of
this assessment.

Two properties make it suitable:

- **It needs no password.** Reading configuration needs no account, so an assessment
  needs no credentials on the system it assesses.
- **It only reads.** There is no way for it to change a setting.

One caution recorded for anyone verifying by hand: `btool check`, which reports invalid
settings, exits successfully even when it has found problems. Its output is the result;
its exit status is not. This assessment reads the output.

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
