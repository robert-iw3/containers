# Configuration specification

Every setting this integration writes into `savedsearches.conf`, what it is
for, and why it is set that way. Written for someone who will have to
operate, review or change it.

Settings quoted from `savedsearches.conf.spec` are from Splunk Enterprise
10.4.2.

---

## 1. How a detection fires

### `counttype`, `relation`, `quantity`

```ini
counttype = number of events
relation = greater than
quantity = 0
```

The alert fires when the search returns more than zero results.

These are the conf-file names. The REST API calls the same three settings
`alert_type`, `alert_comparator` and `alert_threshold`, and those names are
rejected here. The failure is quiet rather than loud: `counttype` defaults
to `always`, so a stanza using the REST names fires on every run regardless
of results, and looks like a detection problem rather than a configuration
one.

### `alert.digest_mode = 1`

> A value of "true" means that the Splunk platform applies the alert actions
> to the entire result set.

Alert actions run once per search, not once per result. With per-result
actions a burst of eighty matches sends eighty notifications. The searches
here aggregate before alerting, so one firing is one finding either way, but
the setting is stated rather than inherited.

---

## 2. Scheduling

### `realtime_schedule = 0`

This is a correctness setting, not a tuning preference.

> When set to 'true', the scheduler might skip some execution periods to
> make sure that the scheduler is executing the searches that are running
> over the most recent time range.
>
> Use continuous scheduling whenever you enable the 'summary index' option.

The default is `true`. Every detection search here ends in `collect`, which
is summary indexing. Left at the default, a loaded scheduler silently drops
execution periods: the detections in those windows are never found, and the
detection index has gaps that nothing reports.

With `0`, the scheduler computes the next run from the last run rather than
from the clock, so no period is skipped. Searches can fall behind under
load, which for detection is the right trade.

### `cron_schedule` and `allow_skew`

```ini
cron_schedule = */10 * * * *
allow_skew = 100%
```

> Lets the search scheduler randomly distribute scheduled searches more
> evenly over the scheduled time periods.

Five hundred searches all asking for minute zero will overrun the
instance's concurrency limit. `allow_skew` is the supported way to spread
them, and the scheduler does the distribution.

It applies only to `* * * * *` and `*/M * * * *` crons. Writing a
hand-computed `0,10,20,30,40,50` cron to spread the load defeats it, because
that form is never skewed. The cron is deliberately left simple so the skew
applies.

### `schedule_priority` and `schedule_window`

| Disposition | Setting | Why |
|---|---|---|
| immediate | `schedule_priority = higher` | a severe, specific detection should not queue behind hundreds of trend searches |
| trend | `schedule_window = auto` | it has no precise start time, so the scheduler may place it where there is room |

`schedule_window` is not set on immediate rules: a search feeding a summary
index wants a predictable cadence.

### `dispatch.earliest_time` and `dispatch.latest_time`

The search window should match the cron interval. A `*/10` schedule with a
`-10m` window examines each event once. A window wider than the interval
re-examines the same events on every run and writes the same detection
repeatedly.

The lab configuration widens the window deliberately, because the dataset is
a fixed body of history rather than a live feed. That is a lab setting and
is wrong for production.

---

## 3. Suppression

```ini
alert.suppress = 1
alert.suppress.period = 1h     # immediate
alert.suppress.period = 24h    # trend
alert.suppress.fields = host
```

Suppression is per host. The same rule firing on a second host is a
different finding and should not be silenced by the first.

An immediate rule uses the shorter period because it is meant to be seen
again if it recurs. A trend rule uses a day, because its value is in the
pattern rather than in each occurrence.

Suppression affects alert *actions*, not the written detection event. The
index keeps every occurrence, so the trend stays complete even while
notifications are throttled.

---

## 4. What a detection event contains

Every search ends by aggregating, labelling and writing:

```spl
| stats count as sigma_match_count,
        min(_time) as sigma_first_seen,
        max(_time) as sigma_last_seen,
        earliest(_raw) as sigma_sample,
        values(index) as sigma_src_index,
        values(sourcetype) as sigma_src_sourcetype,
        dc(host) as sigma_host_count
  by host
| where sigma_match_count >= <threshold>
| eval _time=sigma_first_seen, ...
| collect index=sigma_alerts sourcetype=sigma:alert
```

### Why aggregate

Without the `stats`, a rule matching eighty failed logons writes eighty
detection events: eighty repetitions of one fact. Aggregating by the entity
the detection concerns produces one finding that says eighty, which is what
triage needs.

### Why `_time = sigma_first_seen`

`collect` would otherwise stamp the event with the search time. Setting it
to first seen places the detection at the start of the activity, so the
timeline reflects when it happened rather than when it was noticed.

### Why the origin fields are captured before `collect`

`collect` rewrites `index` and `sourcetype` to the destination. Captured
afterwards they would read `sigma_alerts` and `sigma:alert`, and the trail
back to the log that matched would be gone. `sigma_src_index`,
`sigma_src_sourcetype` and `sigma_src_host` are what the dashboard drilldown
uses.

### Fields written

| Field | Meaning |
|---|---|
| `sigma_rule`, `sigma_rule_id` | which rule, and its Sigma UUID |
| `sigma_level`, `sigma_severity` | the rule's declared criticality, and that mapped to Splunk's 1–5 |
| `sigma_confidence`, `sigma_confidence_score` | how far the rule can be trusted on a single match |
| `sigma_disposition` | `immediate` or `trend` |
| `sigma_attack`, `sigma_tactic` | ATT&CK techniques and tactics |
| `sigma_match_count` | how many events matched in this group |
| `sigma_first_seen`, `sigma_last_seen`, `sigma_span_seconds` | when, and over how long |
| `sigma_sample` | the earliest matching raw event |
| `sigma_src_index`, `sigma_src_sourcetype`, `sigma_src_host` | where to pivot back to |
| `sigma_host_count` | how many hosts the group covers |

---

## 5. Criticality and confidence

Criticality alone is a blunt instrument. A critical rule whose own author
has written down that it fires on legitimate work should not page anyone on
a single event; a specific rule for a named tool should.

Confidence is scored from what the rule declares about itself. Each stanza
carries its own scoring as comments, so a decision can be audited without
re-running the converter:

```ini
# confidence medium (43/100) -> trend
#   status test (-5)
#   author declares 1 known false positive(s) (-8)
#   2 specific value match(es)
```

| Signal | Effect | Reasoning |
|---|---|---|
| `falsepositives` declares known FPs | −8 each, to −24 | the strongest signal available: the author is stating that legitimate activity matches. 652 of SigmaHQ's 1377 core rules declare at least one |
| condition contains a `not` filter | +10 | the author found those false positives and excluded them |
| `status: stable` | +15 | it has survived review |
| `status: deprecated` | −25 | it has not |
| three or more field constraints | +5 each, to +20 | a narrower claim |
| a single field constraint | −10 | a broad one |
| `contains` on a string under six characters | −5 each, to −15 | matches a great deal of unrelated text |
| exact or `endswith` match of twelve or more characters | +3 each, to +10 | matches one thing |

Score 60 or above is high, 35 to 59 medium, below 35 low.

### Disposition

```
immediate  =  level in (critical, high)  AND  confidence == high
trend      =  everything else
```

| | immediate | trend |
|---|---|---|
| threshold | 1 match | 2 matches |
| alert action | yes | no |
| suppression | 1 hour | 24 hours |
| scheduling | `schedule_priority = higher` | `schedule_window = auto` |

A trend rule still records every detection. It simply does not notify;
its value is read from the baseline and the anomaly searches.

Against SigmaHQ's 558 Windows process-creation rules this disposes as 211
immediate, 283 medium-confidence trend, and 64 low-confidence trend.

---

## 6. The engine searches

Three searches ship with the app, separate from the converted rules.

| Search | Schedule | Purpose |
|---|---|---|
| `Sigma - Daily detection rollup` | 01:20 | per rule, host and day into `sourcetype=sigma:rollup`, so trend views read a rollup instead of re-aggregating the detection index |
| `Sigma - Detection volume anomaly` | 01:40 | a rule exceeding its own fourteen-day mean by more than three standard deviations |
| `Sigma - First seen on host` | 01:50 | a rule firing on a host it has not fired on in fourteen days |

The anomaly search compares a rule against **its own** history, so a rule
that is always noisy is not flagged for being noisy, only for changing. The
first-seen search covers the opposite case: one event on a host that has
never produced this detection can matter more than a hundred on a familiar
one.

---

## 7. Tuning

Tuning belongs in the `sigma_allowlist` lookup, not in the rules. A packaged
rule edited in place is silently reverted by the next reinstall; a lookup is
instance state and survives.

| Column | Meaning |
|---|---|
| `sigma_rule_id` | the rule to allowlist, or blank for every rule |
| `sigma_src_host` | the host, or blank for every host |
| `reason`, `added_by`, `added_on` | why, who and when — so an entry can be reviewed later |

The `sigma_detections` macro applies it, and every dashboard reads through
that macro, so an entry takes effect everywhere at once.

To disable a rule outright, set `disabled = 1` in
`local/savedsearches.conf` rather than editing the packaged file.
