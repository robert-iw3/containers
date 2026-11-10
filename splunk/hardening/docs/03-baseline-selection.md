---
title: "Splunk Hardening Toolkit"
subtitle: "Baseline selection: which requirements govern, and why"
author: "Security Control Assessment"
date: "2026-11-09"
---

# Baseline Selection

Before any finding is worth reading, one question has to be settled: **which security
requirements govern this product?** A checklist built from the wrong baseline is wrong
in every row.

This document states which baselines were selected, what the selection rests on, which
part of it is DISA precedent and which part is our own determination, and what about it
is still unfinished.

## Why a baseline has to be selected at all

DISA has published exactly one product STIG for Splunk: the **Splunk Enterprise 8.x for
Linux STIG, V2R3**, benchmark date 02 July 2025. It is **sunsetted** - DISA no longer
maintains it.

There is no current product STIG for Splunk. So the governing requirements fall back to
the Security Requirements Guides, which are maintained. That fallback is why a selection
has to be made and defended rather than simply named.

The version gap points the same way. The sunsetted STIG addresses Splunk 8.x. The
instance assessed here runs Splunk Enterprise 10.4.2.

## SRG and STIG

**An SRG - a Security Requirements Guide - states requirements for a whole category of
product.** It says what must be true, in technology-neutral words: a central log server
must protect its audit records, a web server must limit simultaneous session requests. It
does not say which setting to change, because it does not know which product you have.

**A STIG is the product-specific version of those requirements.** DISA takes an SRG
requirement and writes the exact file, setting, and command for one named product.

When a product has a current STIG, the translation work is DISA's and already done. When
it does not, the SRG is still the governing document, but **translating each requirement
into Splunk settings becomes the assessor's work**. That translation is what this toolkit
records, which is why every finding states the setting it read and how much confidence
stands behind the reading. `02-how-it-decides.md` covers that.

## The evidence from DISA's own Splunk STIG

The sunsetted STIG is the best available evidence of how DISA itself categorized Splunk.
Each of its rules names the SRG requirement it was derived from, so the question can be
answered by counting.

| | |
|---|---|
| Rules in the Splunk Enterprise 8.x for Linux STIG V2R3 | **37** |
| Rule identifiers | all `SPLK-CL-xxxxxx` |
| Distinct SRG requirements they derive from | **36** |
| Derived from **Central Log Server** SRG requirements | **36 of 36** |
| Derived from **Web Server** SRG requirements | **0** |

Thirty-seven rules map to thirty-six requirements because one requirement,
`SRG-APP-000391-AU-002290`, received two rules.

DISA treated Splunk as a central log server and nothing else. Every rule it wrote carries
a Central Log Server SRG identifier, and the `CL` in its own `SPLK-CL-` identifiers says
the same thing. No rule in it derives from the Web Server SRG.

The sunsetted STIG is kept in `benchmarks/` and parsed into the inventory alongside the
two SRGs - 290 rules in `assess/inventory/srg-rules.json`, being 127 plus 126 plus 37 -
so anyone can re-run that count instead of taking it on trust. It contributes no rule
file and produces no finding.

## The determination

Two baselines govern this assessment.

| Baseline | Version | Benchmark date | Requirements | Identifier form | Basis |
|---|---|---|---|---|---|
| Central Log Server SRG | V3R5 | 30 Sep 2026 | 127 | `SRG-APP-xxxxxx-AU-xxxxxx` | DISA precedent |
| Web Server SRG | V4R5 | 01 Jul 2026 | 126 | `SRG-APP-xxxxxx-WSR-xxxxxx` | **our determination** |

The assessed rule set is **253 requirements, exactly the union of those two** - one rule
file per requirement in `assess/rules/`. Nothing was added and nothing was omitted; this
was verified by comparing the two sets, and it holds in both directions. The two baselines
share no requirement identifier, which is why 127 plus 126 is 253 and not less.

### The Central Log Server SRG is settled

It is what DISA applied to this product, and it matches what Splunk is used for here:
the place audit records are sent so they can be kept, protected and reviewed.

### The Web Server SRG is our addition

**Including the Web Server SRG is our determination, not DISA precedent.** An assessor
has to be able to see that and to challenge it, so it is stated plainly rather than
folded into the total.

The technical basis is that this product serves two HTTP interfaces of its own:

- **Splunk Web** - the browser interface people sign in to and run searches from. Default
  port 8000.
- **splunkd** - the management service, which also answers a REST interface used by
  administrative tools and by other Splunk instances. Default port 8089.

Both are web servers reached over the network. Web Server SRG requirements - session
limits, TLS protocol versions, cipher selection, what the server discloses in an error -
describe exactly those interfaces, and Splunk has settings for them. Judging the two
ports against no web server baseline would leave a real, exposed attack surface
unassessed.

The counter-argument deserves to be recorded: DISA, with the same product in front of it,
did not do this. Our answer is that the Web Server SRG requirements land on settings
Splunk actually has, and that an assessment that reads them is more useful than one that
does not.

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

Both appear in the sunsetted STIG. Neither appears in Central Log Server SRG V3R5 or in
Web Server SRG V4R5. So neither has a rule file here, and neither is assessed.

That is not an omission. A requirement that is in no current baseline is not a current
requirement. It is recorded because anyone comparing this assessment against the old
STIG will find two of its thirty-seven rules unanswered, and this is why. The other
thirty-four derivation identifiers are in Central Log Server SRG V3R5 and are assessed.

## The Web Server SRG question, settled by precedent

Including the Web Server SRG was this assessment's own determination. DISA's Splunk
STIG derived nothing from it, which is a fair challenge to answer.

Three other product STIGs held in `stig_viewer/library` answer it. Dragos Platform,
Tanium and Xylok Security Suite are security platforms administered through a web
interface, as Splunk is. Counting the requirements each cites that exist **only** in
the Web Server SRG, and not in the Central Log Server SRG:

| Product STIG | SRG-APP requirements cited | Web-Server-only |
|---|---|---|
| Xylok Security Suite 20.x | 142 | **16** |
| Tanium 7.x | 72 | **15** |
| Dragos Platform 2.x | 62 | **8** |
| Splunk Enterprise 8.x | 42 | **0** |

Every comparable platform draws on Web Server requirements. Splunk's STIG is the one
that does not. The precedent supports inclusion, and the omission in the Splunk STIG
looks like a gap in that document rather than a determination that the Web Server SRG
does not apply.

This is reproducible: the base requirement identifiers are in the XCCDF files, and a
requirement carrying a `-WSR-` identifier and no `-AU-` equivalent belongs to the Web
Server SRG alone.

## Baseline tracker

An SRG governs a product that **performs** that function as a service to others - not
one that merely uses or contains the capability. Splunk authenticates users but is not
an authentication service; it stores data but is not a database; it exposes an API but
is not an API platform. That rule settles every candidate.

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
