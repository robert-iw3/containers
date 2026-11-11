# Proving the deployment works

A detection product that is quiet and a detection product that is broken
look identical from the outside. Both show an empty dashboard. The only way
to tell them apart is to put activity through it that you labelled
yourself, and see what comes back.

That is what this is for. Install the app in your environment, point this
at the instance, and it answers the questions that decide whether you can
trust what the dashboards tell you.

```bash
./test/run-all.sh --container <splunk-container> --uf <forwarder-container>
./test/run-all.sh --local
```

Exit status is zero only if every phase passed. A phase that could not run
reports as skipped, never as passed.

---

## What each phase proves

### 0. The labelled data — `test/check-dataset.py`

Every number the later phases report is measured against labels. If the data
disagrees with its own record of what was planted, those numbers are unsafe
to read whatever they say.

Four checks, offline, on a dataset `scenario.py` has just written:

| Check | Why it matters |
|---|---|
| no event dated ahead of the run | Splunk re-times anything past `MAX_DAYS_HENCE` to its ingest time, so a future-dated event lands in the engine's live window whatever its recorded timestamp — and a round can score a detection the engine would not have made on correctly dated data |
| every event inside the declared window | an event outside it is one no search aimed at that window will see |
| each instance's window covers its own events | a scorer matches a detection to the instance whose window contains it, so a window stopping short of its own campaign turns a real detection into a miss |
| the counts agree | if `planted_records` does not match the instances, the ground truth has lost track of what it planted |

Attribution is exact rather than by time: the ground truth records a sha1
prefix per planted event, so each line is matched to the instance that
produced it.

All three of the first kinds of fault have been found in practice, and the
checker exists because each was invisible in the result it corrupted.

### 1. The rule set — `bin/preflight.py`

Runs without Splunk. Answers the questions that have each cost a
deployment cycle here: does every rule convert, are the ids unique, does
every generated search parse, is every log source mapped to where it is
indexed, do the rules reference fields this environment actually produces,
and can the instance carry the schedule it is being given.

The last one matters most. Several hundred scheduled searches against an
instance that allows four concurrent is the failure this integration was
built around: the scheduler defers almost everything, reports no error, and
the dashboards read zero.

### 2. The instance — `bin/check-instance.sh`

Checks what preflight cannot, because it is a property of the installation
rather than of the rules. Whether any app has set `[default] disabled = 1`
in `inputs.conf` — which is a default for *every* input on the instance,
and has disabled the spool input that summary indexing depends on, so
searches ran, matched, and wrote results that nothing ever read. Whether
concurrency can carry the schedule. Whether the destination indexes exist.
Whether structured parsing is configured where the files are actually read,
which is the forwarder, not the indexer.

### 3. Detection — `test/synthesize.py` and `test/validate-round.py`

The control round runs first. It plants nothing, so every detection it
produces is a false positive with no ground truth to confuse it. A noisy
rule set shows up here before recall is measured, which is the right order:
recall on a set that floods the queue is not a useful number.

Then four tiers. The matching event is identical in each; what changes is
how hard it is to notice.

| tier | placement | signal |
|---|---|---|
| t1 | repeated, obvious indicators | ~3% of the batch |
| t2 | inside a plausible parent chain | ~1% |
| t3 | legitimate parent, one occurrence, spread through the window | ~0.3% |
| t4 | a single event in twelve thousand | ~0.07% |

A rule caught at t1 and missed at t4 is not a rule defect. It is a
statement about aggregation thresholds and search windows, and that is what
the tiers exist to measure.

**How the ground truth is made honest.** `synthesize.py` constructs an
event that satisfies a rule's detection block, renders it in the wire
format the add-ons parse, reads it back with an independent parser, and
evaluates the rule's condition against the result. Only an event that
survives that round trip is offered as ground truth.

The ordering is the point. If the evaluator disagrees, the synthesiser is
wrong and nothing has been learned about Splunk. If the evaluator agrees
and Splunk misses it, the fault is in the Splunk path and the test has
found something real. On its first run the evaluator rejected 537 of 558
rules, correctly: the offline parser matched `<Data Name="x">` with double
quotes, and Windows writes single quotes, so it had been unable to read
Windows event XML at all.

Each round labels its events with its own host at the input, so a detection
belongs to exactly one round and nothing is inferred from timing.

### 4. The dashboards — `test/qa-dashboards.py`

A dashboard that errors shows the error in a panel and nowhere else. Nobody
reads eight dashboards' worth of panels after every change. This extracts
the query from all 93 panels, resolves the tokens, reassembles
post-process panels onto their base search, runs them all and reports which
errored.

A panel returning no rows is reported separately from one that errored. An
empty panel can be correct; an error never is, so the two are not summed.

Panels whose purpose is to write are listed as skipped, because exercising
them would append to the case journal, and a test that mutates the record
it is checking is not a test.

---

## Reading the result

**Recall** is the number usually quoted. A low value means an intrusion
goes unseen.

**False positives on the control** is the number that decides whether the
app is usable. A low-precision detection product costs an analyst their
week and then costs you their attention permanently, which is worse than
the missed detection because it does not come back.

Both are reported, and the rules that were missed and the rules that fired
spuriously are named rather than counted.

---

## When a round fails

Work outward from the narrowest check:

1. **preflight failed** — the rule set, not the instance. Read the reason.
2. **instance check failed** — nothing can be written. Fix that before
   reading any detection number, because they will all be zero.
3. **control produced false positives** — the named rules are firing on
   ordinary activity. Allowlist them, or ask whether the log source mapping
   is sending them data they were never meant to see.
4. **recall below 100%** — the missed rules are named with their id. The
   event was proven to match offline, so the fault is between ingest and
   the summary index: parsing, scope, scheduling, or the window.
5. **a dashboard panel errored** — the panel is named. It is a reporting
   fault, not a detection one, so detections are unaffected.

---

## Health alerts while staging data

Staging a dataset pushes a hundred thousand backdated records through a
single-node instance in a few minutes. Splunk's own health check reports it,
and two of the three are the staging itself rather than a defect:

| Alert | What it means here |
|---|---|
| **System IOWait** (yellow at 1) | the ingest. A hundred thousand records is a few seconds of disk; the indicator is sensitive by design and clears on its own |
| **Forwarder Ingestion Latency** | lab events are backdated across the window, so the gap between event time and index time is the window width. Inherent to backdated data, and it clears once staging stops |
| **Searches Delayed** | more scheduled searches than the instance can run at once. This one is **not** inherent -- it means searches were left installed. The harnesses remove their own apps when they finish; `bin/check-instance.sh` reports the real concurrency limit |

An ingestion-latency gap far wider than the window is worth reading rather
than dismissing. It is what exposed a generator fault: a scenario whose
campaign was longer than the window had its later steps dated weeks ahead,
and Splunk re-times anything past `MAX_DAYS_HENCE` to its ingest time -- so
those events landed in the engine's live window whatever their recorded
timestamp, and a round could score a detection the engine would not have
made on correctly dated data. `scenario.py` now refuses to plant a campaign
it cannot fit and names the window each would need.

## Files

| path | what it is |
|---|---|
| `run-all.sh` | the whole sequence, with a verdict |
| `synthesize.py` | builds events a named rule must match, and proves it offline |
| `validate-round.py` | puts a batch through a live instance and scores it |
| `qa-dashboards.py` | runs every dashboard panel search |
| `score-dataset.py` | scores a rule set against a labelled dataset, offline |
| `rules-against-data.py` | runs rules over a dataset without Splunk |
| `batches/`, `results/` | generated; not tracked |
