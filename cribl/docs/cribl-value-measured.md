# What Cribl is worth in front of Splunk: a measured A/B

Every number in this document was produced by `cribl/integration-lab/run-lab.sh`
on a running stack. Nothing here is a vendor figure, and the projection inputs
that are *not* measured are labeled as such where they appear.

Run: 15 log sources, 30,000 records, 41 assertions, 0 failed.

## What this run was built to prove

One question: **how much indexed volume — and therefore license cost — a Cribl
pipeline removes in front of Splunk.** It is an index-utilization measurement.
It is not an assessment of detection coverage, and it does not claim the
resulting data set is sufficient for one.

Two limits follow from that, and both matter when reading the numbers:

- **The Windows Security event IDs here are an example set**, chosen to exercise
  the pipeline across a realistic spread of record shapes and volumes. They are
  not a detection baseline. An environment selects its channels and event IDs
  from its own threat model, its logging standard and the analytics it actually
  runs. Nothing in this document should be read as a recommendation of which
  Windows events to collect.
- **The reduction rules were held to one coverage rule** — one full-rate witness
  per domain — but applied only to the fifteen sources this run carries. The
  rule is transferable; these specific rules are not.

---

## 1. Method

Splunk licenses on **indexed volume** — the bytes of `_raw` as they land. So the
lab measures the same quantity twice, on the same records, in the same run:

```
                        +--> Cribl worker --> pipeline --> HEC --> index=enterprise       (arm B)
 log source emitter --tee --|
                        +--------------------------> HEC --> index=enterprise_raw         (arm A)
```

Every record goes down both paths. Arm A is what a forwarder pointed straight at
Splunk would have indexed; arm B is what arrives after the pipeline. Both are
then read back **out of Splunk** with the same search — `| eval b=len(_raw) |
stats count sum(b)` — so the baseline is measured, not computed from what the
emitter says it sent.

Three checks gate the comparison. The run fails if any check fails:

- the control arm received all 30,000 records, with zero HEC errors;
- the emitter's own byte count and the control index agree to within 1% — two
  independent measurements of the same quantity;
- the indexer is indexing and the searching account can see it — `index_thruput`
  non-zero **and** `index=_internal` returning events, because those are two
  different failures that look identical from a search.

## 2. The log sources

Fifteen sources, weighted by their **share of total bytes** — the way SIEM
volume is quoted — not by event count. Record sizes differ by a factor
of twelve across these feeds, so the harness measures each source's average size
and solves for the selection weight that lands on the declared share.

The shares are engineering estimates for a ~10,000-endpoint enterprise. They are
the single most consequential assumption here, because the reduction a pipeline
achieves is mostly a property of what the environment sends it.

## 3. What tuning for volume costs in detection

An earlier version of this rule set removed **69.8%**. It did that by sampling
Sysmon network connections 1:5 while also dropping Security 5156/5158, sampling
DNS by name, sampling firewall and VPN session records, and masking encoded
PowerShell payloads in place.

Each of those removes a detection capability:

| Rule | What it cost |
| --- | --- |
| Sample Sysmon 3 **and** drop 5156/5158 | No full-rate record anywhere of which process opened which connection |
| Sample DNS by name | Beaconing to a CDN-fronted or compromised legitimate domain falls in the sampled set |
| Sample firewall / VPN / flow records | Beaconing reads intervals between connections; a 1-in-N sample gives a wrong answer, not a coarse one |
| Mask `-EncodedCommand` in place | Destroys the artifact an analyst decodes first, for 7 bytes an event |
| Drop web 2xx by file extension | A webshell reached at a static-looking path is discarded |

Removing those rules costs **half the saving**: 69.8% becomes 34.4%. That
difference is the price of the visibility, stated so it can be argued with
rather than discovered during an incident.

Where volume still comes from is the part that survives scrutiny: dropping a
record class that has a full-rate substitute, removing fields nothing reads, and
sampling only what genuinely duplicates a source kept whole.

## 3.1 Result

| | Events | Licensed volume |
| --- | ---: | ---: |
| **A** — endpoints → Splunk, no pipeline | 30,000 | 12.97 MB |
| **B** — endpoints → Cribl → Splunk | 17,692 | 8.50 MB |
| **Removed** | 12,308 (41.0%) | 4.47 MB (**34.4%**) |

On disk, the same two indexes measure 6.59 MB against 4.11 MB. That is a
lab-scale figure dominated by tsidx overhead on small hot buckets, not a
production compression ratio, and it is not used anywhere below.

### Where the saving comes from

Six of fifteen sources are not reduced at all, and that is the design rather
than an omission. Each is either the only witness to something or is small
enough that reducing it buys nothing worth the coverage risk.

| Source | Before | After | Removed | Treatment |
| --- | ---: | ---: | ---: | --- |
| Windows Security | 2,204 KB | 897 KB | 59.3% | drop 5156/5158 · route encoded commands to a restricted index |
| NetFlow | 1,209 KB | 60 KB | 95.0% | sample 1:20 — duplicates the firewall for perimeter traffic |
| Kubernetes stdout | 1,075 KB | 150 KB | 86.1% | drop INFO and DEBUG except lines carrying auth content |
| Suricata EVE | 974 KB | 403 KB | 58.7% | alerts and http whole · flow sampled 1:10 |
| Web proxy | 664 KB | 419 KB | 36.8% | strip the user-agent string · nothing dropped |
| Windows DNS Analytical | 2,103 KB | 1,913 KB | 9.0% | strip PacketData · no sampling |
| Web tier | 794 KB | 671 KB | 15.5% | drop GET 2xx for static paths only · never a POST |
| Cisco ISE | 372 KB | 306 KB | 17.7% | strip the Step= state-machine chain |
| Windows DHCP | 25 KB | 25 KB | 0.0% | none |
| Sysmon | 506 KB | 506 KB | 0.0% | none — full-rate host network witness |
| Windows System / Defender | 255 KB | 255 KB | 0.0% | none |
| Entra ID sign-in | 17 KB | 17 KB | 0.0% | none |
| Cisco ASA / VPN | 137 KB | 137 KB | 0.0% | none — only witness to VPN session volume |
| Linux auth | 96 KB | 96 KB | 0.0% | none |
| Palo Alto | 2,854 KB | 2,854 KB | 0.0% | none — full-rate perimeter witness |
| **Total** | **12.97 MB** | **8.50 MB** | **34.4%** | |


The rule the set is built on: **one full-rate witness per domain, reduce the
duplicates.** The Palo Alto log is kept whole as the perimeter witness, so
NetFlow and Suricata flow — which record the same connections with less
context — are reduced. Sysmon EventID 3 is kept whole as the host witness, which
is what makes dropping Security 5156/5158 defensible.

## 4. What an endpoint-side filter would have done on its own

This comparison determines whether Cribl reduces volume beyond what a universal
forwarder can do on its own, and it is the first objection a Splunk engineer
will raise.

A universal forwarder can drop events at the endpoint with an `inputs.conf`
`blacklist` — `blacklist1 = $XmlRegex="<EventID>(?:5152|5153|5156|5158)</EventID>"`
is in this repository's own design document. It costs nothing and needs no
Cribl. Measured against the same data set:

| | Licensed volume removed | Share of the total saving |
| --- | ---: | ---: |
| UF blacklist on 5156/5158, no Cribl | 9.7% of total volume | 28.2% |
| Cribl's marginal contribution over that | 24.7% of total volume | **71.8%** |

The constraint is the blacklist's scope: `$XmlRegex` matches only raw XML on
one Windows channel. It cannot sample a firewall's allowed sessions
while keeping every deny, it cannot strip one field out of a DNS record, it
cannot drop INFO from a container's JSON, and it cannot redact. Only one of the
treatments in the table above can be expressed at the endpoint.

**Within Windows Security events, the endpoint blacklist captures nearly all of
the available saving at no cost. Across all fifteen sources it accounts for
13.9% of the total saving; the remaining 86.1% comes from treatments the
endpoint cannot express.**

## 5. What the reduction costs, per control

A volume reduction figure is incomplete without a control coverage figure beside it. Each source
in the lab declares which NIST SP 800-53r5 controls and CSF 2.0 subcategories
its events evidence, and which of those must not be dropped. After reduction,
the run asserts that every one of them still has evidence in the index.

**The lab covers 37 distinct 800-53r5 controls across 71 control-to-source
mappings. After reduction, all 71 mappings still have evidence in the index.** The lab
asserts the 71 mappings; the table below collapses them to the 37 controls.

| 800-53r5 | CSF 2.0 | Evidenced by |
| --- | --- | --- |
| AC-2 | PR.AA-01 | win_security |
| AC-2(12) | DE.CM-01 | win_security |
| AC-2(7) | PR.AA-05 | win_security |
| AC-3 | PR.AA-05 | win_security |
| AC-4 | PR.IR-01 | proxy |
| AC-6(9) | PR.AA-05 | linux_audit, win_security |
| AC-7 | DE.CM-01 | cisco_ise, entra_signin, linux_audit, win_security |
| AC-17 | PR.AA-05 | asa_vpn, cisco_ise, entra_signin, linux_audit, pan_firewall, win_security |
| AC-17(1) | PR.AA-05 | asa_vpn |
| AU-2 | DE.AE-03 | win_security |
| AU-3 | DE.AE-03 | win_security |
| AU-3(1) | DE.AE-03 | win_security |
| AU-9 | PR.PS-04 | win_security |
| AU-9(4) | PR.AA-05 | win_security |
| AU-12 | DE.CM-01 | entra_signin, linux_audit, win_dhcp, win_security |
| CM-3 | PR.PS-01 | win_security |
| CM-5 | PR.PS-01 | win_security |
| CM-7 | PR.PS-02 | sysmon, win_security, win_system |
| CM-7(2) | PR.PS-02 | win_system |
| CM-8 | ID.AM-01 | win_dhcp |
| CM-8(3) | ID.AM-01 | win_security |
| CP-10 | RC.RP-01 | win_system |
| IA-2 | PR.AA-02 | cisco_ise, entra_signin, linux_audit, win_security |
| IA-2(1) | PR.AA-03 | entra_signin |
| IA-3 | PR.AA-01 | cisco_ise, win_dhcp |
| IA-5 | PR.AA-01 | win_security |
| IR-4 | RS.MA-01 | win_system |
| IR-4(1) | RS.MA-02 | win_system |
| MA-2 | ID.AM-08 | win_system |
| MA-4 | PR.AA-05 | asa_vpn, win_system |
| MP-2 | PR.DS-01 | win_security |
| MP-7 | PR.DS-01 | win_security |
| SC-7 | PR.IR-01 | asa_vpn, pan_firewall, proxy, suricata, web_access, win_dns, win_security |
| SI-3 | DE.CM-01 | win_system |
| SI-4 | DE.CM-01 | pan_firewall, proxy, suricata, sysmon, web_access, win_dns, win_security |
| SI-4(4) | DE.CM-09 | suricata, win_dns |
| SI-7 | PR.DS-06 | sysmon, win_security, win_system |


The check is only as good as the map, and the map is hand-authored from the
control text and corroborated against a separate research pass over 106
mappings. It is not an audit opinion. It does fail the run if a
pipeline edit removes a control's only evidence, a gap that would otherwise
surface at an audit months later.

Four sources are reduced by 0.0% on purpose. Two of them, Entra sign-ins and
Linux authentication, are small and consist almost entirely of control evidence. A pipeline
that trims every source equally is tuned to a volume target rather than to the
value of each source's events.

## 6. The encoded-command result, which is not a volume result

The Windows pipeline routes PowerShell `-EncodedCommand` events to a restricted
index rather than masking the payload in place. Searching all three indexes for
that payload:

| Index | Events carrying the payload |
| --- | ---: |
| `enterprise_raw` — no pipeline | 13 |
| `enterprise` — main index | **0** |
| `enterprise_restricted` — routed | **13** |

An earlier version masked it. That saved seven bytes an event and destroyed the
artifact an analyst decodes first when the alert fires. The exposure this
controls is real — legitimate automation uses `-EncodedCommand` and the payload
can carry credentials and connection strings — but the control for that is
access and retention on a separate index, not deletion.

The unfiltered index is what a forwarder pointed straight at Splunk would have
written, and it holds the payload in plaintext for as long as that index
retains. Routing bounds who can read it. Masking would have bounded who can
respond to it.

## 7. Projection, and exactly which parts are measured

The reduction ratio and the average record size are measured; the fleet rate and
the license price are inputs.

| Quantity | Value | Where it comes from |
| --- | ---: | --- |
| Reduction ratio | 34.4% | **measured**, this run |
| Average record size | 453 bytes | **measured**, this data set — a property of these 15 synthetic sources |
| Fleet rate | 56,750 EPS | *input* (`LAB_FLEET_EPS`): 10,000 × 5 + 55 × 50 + 5 × 800, modeled |
| License price | $150 / GB/day / year | *input* (`LAB_COST_PER_GB_DAY`), operator-supplied |

At those inputs: **2,071 GB/day → 1,358 GB/day**, and $310,609 → $203,621. The dollar
figure is arithmetic on three inputs beyond the measured reduction ratio:
average record size, fleet rate and license price. Of those three, only the
record size was measured here, and only on synthetic data. Substitute a real
event mix, a real average record size and a real price before using this figure
in a proposal.

The projection also ignores the cost of Cribl itself — license, compute and the
operational burden of another hop — and it assumes the removed data goes
nowhere. In production, most of the removed data should be routed to lower-cost storage
rather than discarded, and that changes the arithmetic.

## 8. Reproducing it

```bash
cd cribl/integration-lab
./run-lab.sh                 # bring it up, generate traffic, assert, tear down
KEEP_UP=1 ./run-lab.sh       # leave it running
LAB_FLEET_EPS=... LAB_COST_PER_GB_DAY=... ./run-lab.sh
```

The share values are the assumption the whole result rests on. To measure a
different environment, change `SHARE` in the source modules under
`generator/sources/`, or add a module. Each one declares its own record shape, sourcetype, share, control
mappings and nothing else; the harness handles selection, pacing, the tee and
the accounting.

The reduction assertion is two-sided (18–38% of licensed bytes kept, against
~24% predicted by the declared treatments on the declared shares). Without a
lower bound, a pipeline that dropped every event would produce the largest
reduction figure in this document; an assertion no pipeline can fail measures
nothing.

---

## Note on the next run

This run optimized in one direction: remove volume without losing a domain's
only witness. A second run will measure the other direction — extending
detection coverage across these sources, and across event IDs this set does not
carry, while holding the storage reduction. The objective there is the balance
between the two, not the largest reduction figure. Coverage added and volume
returned will both be measured on the same records, the same way this run
measured removal.
