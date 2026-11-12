# Configuration specification

Every setting this integration writes, what it is for, and why it is that
way. Written for someone who will have to operate, review or change it.

Settings quoted from `savedsearches.conf.spec` are Splunk Enterprise 10.4.2.

---

## 1. Why the searches are shaped this way

**One scheduled search per rule does not run.** Splunk caps concurrent
scheduled searches at roughly half of `max_searches_per_cpu × cpus +
base_max_searches`. On a modest indexer that is four. Against 561 of them
the scheduler deferred almost everything — 7,248 scheduler entries, 6,976
of them `continued`, and not one dispatch directory. Nothing errored. The
dashboards read zero, and a zero reads as "nothing happened".

So rules are **batched**. A batch scans its log source once for the union
of its rules' conditions, then names which of them matched:

```spl
`sigma_lab_index` sourcetype=XmlWinEventLog (EventCode=1 OR EventCode=4688)
  ((<rule 1 condition>) OR (<rule 2 condition>) OR …)
| eval sigma_hits = if(searchmatch("<rule 1>"),"<id 1>,","")
                  . if(searchmatch("<rule 2>"),"<id 2>,","") . …
| where sigma_hits!=""
| eval sigma_rule_id = split(substr(sigma_hits,1,len(sigma_hits)-1), ",")
| mvexpand sigma_rule_id
| stats … by sigma_rule_id, host
| lookup sigma_rules sigma_rule_id
```

622 rules deploy as 21 batched searches plus 22 standalone ones.

### Why a delimited string rather than `mvappend`

`mvappend` returns null as soon as **any** argument is null. With fifty
rules in a batch nearly every test is a miss, so an `mvappend` of the
results was null on every event and the `where` that followed discarded all
of it. The engine ran, scanned the right data, matched, and reported
nothing. Concatenating has no multivalue null semantics to get wrong: a
miss contributes an empty string.

### Why some rules are not batched

A rule is batched only if its condition **parses**, **selects something**,
and is **the whole of its matching**. Twenty-two fail one of those:

| reason | what happens instead |
|---|---|
| its SPL starts with a pipeline stage | deployed standalone |
| its matching continues past a pipeline stage | deployed standalone |
| its condition reduces to a bare `*` | deployed standalone |

The third is the one that cost most. Four rules put their whole matching
logic in a trailing `| regex`, so truncating at the pipe left `*`. That is
a valid search clause, so the parser accepted it — and the batch then
matched every event in scope and attributed it to all four. The parser
needed a second question: *"will Splunk parse this"* is not *"does this
narrow anything"*.

Standalone rules run their full pipeline, where Splunk parses the `rex` or
`regex` itself rather than an approximation of it.

---

## 2. Scope — the setting that decides whether this survives a large index

`logsource-scope.yml` maps a Sigma log source to where it is indexed, and
the batch hoists that scope ahead of the rule conditions:

```ini
windows/process_creation: 'sourcetype=XmlWinEventLog (EventCode=1 OR EventCode=4688)'
linux/auditd:             'sourcetype=linux_audit'
```

Without it a batch reads the whole window — all the DNS, all the firewall —
to find process creation. Measured here, scoping cut a batch's read from
161,727 events to 12,396.

Scoping on the rule's own declared log source cannot drop a detection: a
rule needing Sysmon process creation has nothing to say about data that is
not that. It *can* drop one if this file is wrong for the environment,
which is why unmapped rules are reported rather than left to scan.

---

## 3. How a detection fires

```ini
counttype = number of events
relation = greater than
quantity = 0
```

These are the conf names. The REST API calls the same three `alert_type`,
`alert_comparator` and `alert_threshold`, and those are rejected here. The
failure is quiet: `counttype` defaults to `always`, so a stanza using the
REST names fires on every run regardless of results and looks like a
detection problem rather than a configuration one.

### `alert.digest_mode = 1`

> A value of "true" means that the Splunk platform applies the alert actions
> to the entire result set.

Alert actions run once per search, not once per result. The searches here
aggregate before alerting, so one firing is one finding either way, but the
setting is stated rather than inherited.

---

## 4. Scheduling

### `realtime_schedule = 0`

A correctness setting, not a tuning preference.

> When set to 'true', the scheduler might skip some execution periods…
>
> Use continuous scheduling whenever you enable the 'summary index' option.

The default is `true`. Every detection search writes to a summary index.
Left at the default, a loaded scheduler silently drops execution periods:
those detections are never found and the index has gaps nothing reports.

### Cadence by severity

| severity | interval | window | spread | shipped |
|---|---|---|---|---|
| critical | `*/15` | `-15m` | 5m | enabled |
| high | `*/30` | `-30m` | 10m | enabled |
| medium | hourly | `-60m` | 20m | enabled |
| low | every 4h | `-4h` | 60m | **disabled** |
| informational | every 6h | `-6h` | 60m | **disabled** |

The window always equals the interval. A window wider than the interval
re-reads the same events and writes the same detection again; gaps are
prevented by continuous scheduling instead of by overlap.

Each search is given its own minute within that interval. The cron shown
above is the interval; what is written is offset per search, so the
critical tier emits `0,15,30,45` for one search, `1,16,31,46` for the next,
and so on. Every search keeps its interval exactly; only its position in
the interval differs.

This replaced `allow_skew = 100%`, which was wrong in two ways. It applies
only to `* * * * *` and `*/M` crons, so it did nothing for the hourly tier.
More importantly, neither it nor `schedule_window` stops a run being
counted as late: both let the scheduler move a search, which does spread
the load, but the run is still measured against the time it was scheduled
for. Forty searches sharing one minute on an instance that runs four at
once reported almost every run as delayed no matter which was set. Giving
them different minutes is what actually empties the queue.

`schedule_window` is still set, to the spread shown below, so the scheduler
may even out what the offsets do not. It is kept under the interval, since
a deferral longer than the interval can collide with the next run.

`splunk/search_maintenance/bin/search-lint.py` checks all of this against a
live instance, and `search-stagger.py` applies the same treatment to any
other app that needs it.

---

## 5. What a detection contains

```spl
| stats count as sigma_match_count, min(_time) as sigma_first_seen,
        max(_time) as sigma_last_seen, earliest(_raw) as sigma_sample,
        values(index) as sigma_src_index, values(sourcetype) as sigma_src_sourcetype,
        dc(host) as sigma_host_count
  by sigma_rule_id, host
| lookup sigma_rules sigma_rule_id
| eval _time = sigma_first_seen, sigma_src_host = host,
       sigma_corroborated = if(sigma_match_count >= coalesce(sigma_min_matches,1),
                               "yes", "no")
```

**Why aggregate.** Without the `stats`, a rule matching eighty failed
logons writes eighty detections: eighty repetitions of one fact.

**Why `_time = sigma_first_seen`.** Summary indexing would otherwise stamp
the detection with the search time, placing it when it was noticed rather
than when it happened.

**Why the origin fields are captured first.** Summary indexing rewrites
`index` and `sourcetype` to the destination. Captured afterwards the trail
back to the log that matched would be gone; `sigma_src_*` is what the
dashboard pivot uses.

**Why nothing is discarded.** An earlier version dropped a detection whose
match count was below the rule's threshold. The threshold was meant to say
*do not alert on one match*; written as a `where` it said *do not record
one match*, so a trend rule had no trend to read and a careful one-off —
the thing worth catching — was exactly what was thrown away. Everything is
recorded; `sigma_corroborated` carries whether the threshold was met, so
alerting can still demand corroboration without losing the evidence.

### Fields written

| field | meaning |
|---|---|
| `sigma_rule_id` | the Sigma UUID; everything else is joined from the lookup |
| `sigma_rule`, `sigma_level`, `sigma_severity` | name, declared criticality, and that mapped to Splunk's 1–5 |
| `sigma_confidence`, `sigma_confidence_score` | how far the rule can be trusted on a single match |
| `sigma_disposition`, `sigma_min_matches`, `sigma_corroborated` | how it should be handled, and whether it met its own bar |
| `sigma_technique`, `sigma_technique_name`, `sigma_tactic_name` | ATT&CK, with readable names |
| `sigma_match_count`, `sigma_first_seen`, `sigma_last_seen`, `sigma_span_seconds` | how many, when, over how long |
| `sigma_sample` | the earliest matching raw event — the evidence |
| `sigma_src_index`, `sigma_src_sourcetype`, `sigma_src_host` | where to pivot back to |

---

## 6. Which index receives what

| index | holds | written by |
|---|---|---|
| `sigma_alerts` | detections, and nothing else | the batched and standalone searches |
| `sigma_engine_kpi` | rollups, anomalies, engine cost | the engine searches |
| `sigma_cases` | the case journal | Case Work |

The rollup used to write into `sigma_alerts`, and the macro the dashboards
read does not filter by source type, so every rollup row counted as a
detection — each figure inflated by the summarising of itself. Derived rows
go elsewhere now, which is a structural guarantee rather than a filter
every query has to remember.

---

## 7. Criticality and confidence

Criticality alone is blunt. A critical rule whose own author records that
it fires on legitimate work should not page anyone on one event; a specific
rule for a named tool should.

| signal | effect | reasoning |
|---|---|---|
| `falsepositives` declares known FPs | −8 each, to −24 | the author is stating that legitimate activity matches |
| condition contains a `not` filter | +10 | they found those and excluded them |
| `status: stable` | +15 | it has survived review |
| `status: deprecated` | −25 | it has not |
| three or more field constraints | +5 each, to +20 | a narrower claim |
| a single field constraint | −10 | a broad one |
| `contains` on a string under six characters | −5 each, to −15 | matches a great deal of unrelated text |
| exact or `endswith` of twelve or more characters | +3 each, to +10 | matches one thing |

60 and above is high, 35–59 medium, below 35 low.

```
immediate  =  level in (critical, high)  AND  confidence == high
trend      =  everything else
```

| | immediate | trend |
|---|---|---|
| `sigma_min_matches` | 1 | 2 |
| recorded as corroborated | on a single match | once a second match lands in the same run |
| how the pages read it | "act now" | "trend" |

Disposition is the only thing it changes. Both dispositions are scheduled
identically, by severity, and both write to the detection index on every
run; what differs is the number of matches a detection must carry before
`sigma_corroborated` says yes, and how the analyst pages label it. An
earlier version of this table claimed disposition drove alert actions and
scheduling. It does not, and never did in the generated configuration.

Each stanza carries its own scoring as comments, so a decision can be
audited without re-running the converter.

---

## 8. Tuning

Tuning belongs in the `sigma_allowlist` lookup, not in the rules. A
packaged rule edited in place is silently reverted by the next reinstall; a
lookup is instance state and survives.

| column | meaning |
|---|---|
| `sigma_rule_id` | the rule, or blank for every rule |
| `sigma_src_host` | the host, or blank for every host |
| `reason`, `added_by`, `added_on` | why, who and when |

The `sigma_detections` macro applies it and every dashboard reads through
that macro, so an entry takes effect everywhere at once. Case Work names
the rules repeatedly resolved as false positives, with the id ready to
paste.

Allowlist rather than disable. A disabled rule is invisible; an allowlisted
one still records what it caught, and the entry says who stopped looking
and why.
