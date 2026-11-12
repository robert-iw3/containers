---
title: "Splunk Hardening Toolkit"
subtitle: "Baseline selection: which requirements govern, and why"
author: "Security Control Assessment"
date: "2026-11-09"
---

# Baseline Selection

**Which security requirements govern this product?** This document answers that: the
baselines selected, the basis for each, and what is still unfinished.

## Why a baseline has to be selected at all

DISA has published one product STIG for Splunk: the **Splunk Enterprise 8.x for Linux
STIG, V2R3**, benchmark date 02 July 2025. It is **sunsetted** and no longer maintained.
It addresses Splunk 8.x. The instance assessed here runs Splunk Enterprise 10.4.2.

With no current product STIG, the governing requirements fall back to the Security
Requirements Guides, which are maintained. Which SRGs apply has to be determined.

## SRG and STIG

**An SRG - a Security Requirements Guide - states requirements for a whole category of
product.** It says what must be true in technology-neutral words: a central log server
must protect its audit records, a web server must limit simultaneous session requests. It
names no setting, because it does not know which product you have.

**A STIG is the product-specific version of those requirements.** DISA takes an SRG
requirement and writes the exact file, setting, and command for one named product.

Where a current STIG exists, DISA has already done that translation. Where it does not,
the SRG still governs and **translating each requirement into Splunk settings is the
assessor's work**. This toolkit records that translation. Every finding states the setting
it read and the confidence behind the reading; see `02-how-it-decides.md`.

## The evidence from DISA's own Splunk STIG

Each rule in the sunsetted STIG names the SRG requirement it was derived from, so DISA's
own categorization of Splunk can be counted.

| | |
|---|---|
| Rules in the Splunk Enterprise 8.x for Linux STIG V2R3 | **37** |
| Rule identifiers | all `SPLK-CL-xxxxxx` |
| Distinct SRG requirements they derive from | **36** |
| Derived from **Central Log Server** SRG requirements | **36 of 36** |
| Derived from **Web Server** SRG requirements | **0** |

Thirty-seven rules map to thirty-six requirements because one requirement,
`SRG-APP-000391-AU-002290`, received two rules.

DISA treated Splunk as a central log server. Every rule carries a Central Log Server SRG
identifier, and so does the `CL` in `SPLK-CL-`.

The sunsetted STIG is kept in `benchmarks/` and parsed into the inventory alongside the
two SRGs: 290 rules in `assess/inventory/srg-rules.json`, being 127 plus 126 plus 37.
Anyone can re-run that count. The STIG itself contributes no rule file and produces no
finding.

## The determination

Two baselines govern this assessment.

| Baseline | Version | Benchmark date | Requirements | Identifier form | Basis |
|---|---|---|---|---|---|
| Central Log Server SRG | V3R5 | 30 Sep 2026 | 127 | `SRG-APP-xxxxxx-AU-xxxxxx` | DISA precedent |
| Web Server SRG | V4R5 | 01 Jul 2026 | 126 | `SRG-APP-xxxxxx-WSR-xxxxxx` | **our determination** |

The assessed rule set is **253 requirements, exactly the union of those two**, with one
rule file per requirement in `assess/rules/`. The two baselines share no requirement
identifier, so 127 plus 126 is 253. Comparing the two sets against the rule files
confirmed the union in both directions.

The Central Log Server SRG is settled. DISA applied it to this product, and it matches
what Splunk is used for here: the place audit records are sent so they can be kept,
protected and reviewed.

### The Web Server SRG is our addition

**Including the Web Server SRG is our determination, not DISA precedent.** Splunk serves
two HTTP interfaces of its own:

- **Splunk Web** - the browser interface people sign in to and run searches from. Default
  port 8000.
- **splunkd** - the management service, which also answers a REST interface used by
  administrative tools and by other Splunk instances. Default port 8089.

Both are web servers reached over the network. Web Server SRG requirements cover session
limits, TLS protocol versions, cipher selection, and what the server discloses in an
error. Splunk has settings for all of them. Judged against no web server baseline, those
two ports go unassessed.

**If the Authorizing Official rejects the extension**, the effect is contained. The 126
Web Server requirements are their own 126 rule files, named for `-WSR-` identifiers, and
they share no identifier with the log server set. Removing them removes 126 requirements
and their findings and leaves the 127 Central Log Server determinations untouched.

## Two requirements the old STIG used are retired

Two of the thirty-six requirements the 8.x STIG derived from **no longer exist in either
current baseline**:

| Retired requirement | What it asked |
|---|---|
| `SRG-APP-000165-AU-002580` | Prohibit password reuse for five generations. |
| `SRG-APP-000361-AU-000140` | Notify the System Administrator or ISSO. |

Neither appears in Central Log Server SRG V3R5 or in Web Server SRG V4R5. Neither has a
rule file here, and neither is assessed. A requirement that is in no current baseline is
not a current requirement.

This is recorded because anyone comparing this assessment against the old STIG will find
two of its thirty-seven rules unanswered. The other thirty-four derivation identifiers
are in Central Log Server SRG V3R5 and are assessed.

## The Web Server SRG question, settled by precedent

DISA's Splunk STIG derived nothing from the Web Server SRG. Three other product STIGs
held in `stig_viewer/library` bear on that. Dragos Platform, Tanium and Xylok Security
Suite are security platforms administered through a web interface, as Splunk is. Counting
the requirements each cites that exist **only** in the Web Server SRG, and not in the
Central Log Server SRG:

| Product STIG | SRG-APP requirements cited | Web-Server-only |
|---|---|---|
| Xylok Security Suite 20.x | 142 | **16** |
| Tanium 7.x | 72 | **15** |
| Dragos Platform 2.x | 62 | **8** |
| Splunk Enterprise 8.x | 42 | **0** |

Every comparable platform draws on Web Server requirements; Splunk's STIG does not. The
precedent supports inclusion, and the omission reads as a gap in that document rather
than a determination that the Web Server SRG does not apply.

The count is reproducible: the base requirement identifiers are in the XCCDF files, and a
requirement carrying a `-WSR-` identifier and no `-AU-` equivalent belongs to the Web
Server SRG alone.

## Baseline tracker

An SRG governs a product that **performs** that function as a service to others, not one
that merely uses or contains the capability. Splunk authenticates users but is not an
authentication service; it stores data but is not a database; it exposes an API but is not
an API platform. That rule settles every candidate.

| Baseline | Status | Basis |
|---|---|---|
| **Central Log Server SRG V3R5** | **Applies** - 127 requirements, assessed | Splunk is a central log server. All 37 rules of DISA's Splunk STIG derive from it |
| **Web Server SRG V4R5** | **Applies** - 126 requirements, assessed | Two HTTP listeners, and comparable product STIGs cite Web-Server-only requirements. See the section above |
| **Application Security and Development STIG** | **Not applicable** | Governs applications the organization designs and develops. Splunk is commercial software. *Carve-out: custom Splunk apps written in-house are developed code and would fall under it* |
| **General Application (GAPP) SRG** | **Not applicable** | A general application baseline is the fallback where no technology-specific SRG exists. Central Log Server is the specific one and supersedes it |
| **Application Programming Interface (API) SRG** | **Not applicable** | Governs API management platforms and gateways. splunkd's REST interface is an application function on an HTTP listener already governed by the Web Server SRG |
| **Application Server SRG** | **Not applicable** | Governs middleware hosting independently deployed applications - Tomcat, JBoss, WebLogic. Splunk apps are configuration bundles, not deployed applications |
| **Authentication, Authorization and Accounting SRG** | **Not applicable** | Governs AAA services - RADIUS, TACACS+, identity providers. Splunk authenticates its own users and consumes LDAP or SAML; it provides AAA to nothing |
| **Database SRG** | **Not applicable** | Governs database management systems. Splunk's index is a proprietary time-series store with no relational engine and no SQL |
| **Intrusion Detection and Prevention System SRG** | **Not applicable** | Splunk inspects no traffic and blocks nothing. A SIEM consumes the output of detection systems; Enterprise Security correlates and alerts, still not in-line detection |
| **General Purpose Operating System SRG** | **Not applicable** | Governs an operating system. The host is a separate asset in the accreditation, assessed under its own product STIG |
| **General Application Draft SRG V1R0.1** | **Tracking only** | A draft is not an authorization baseline |
| *27 further SRGs* | **Not applicable** | Network devices, cloud, containers, DNS, voice and messaging, endpoint management, virtualization, mainframe, operational technology |

## What this means for the count

**253 requirements, and the baseline is settled.** Two SRGs apply; ten were determined
not applicable; one draft is tracked for publication. The screening record, with source
URLs, is `assess/inventory/srg-applicability.json`.
