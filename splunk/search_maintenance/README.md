# Splunk search maintenance

Tools for the question "why is this search behaving like that", and for
keeping a lot of scheduled searches organised on an instance that can only
run a few at once.

Every script takes the same connection flags, reads the configuration
actually in force rather than guessing, and changes nothing without being
asked.

```bash
./bin/search-lint.py       --container splunk    # what will go wrong
./bin/scheduler-health.py  --container splunk    # what has gone wrong
./bin/search-inventory.py  --container splunk    # what exists
```

## Which script

| I need to | use |
|---|---|
| find scheduling faults before they bite | [`search-lint.py`](bin/search-lint.py) |
| see what the scheduler has actually been doing | [`scheduler-health.py`](bin/scheduler-health.py) |
| list every saved search, or read one in full | [`search-inventory.py`](bin/search-inventory.py) |
| stop searches queueing behind each other | [`search-stagger.py`](bin/search-stagger.py) |
| reclaim the disk search results are using | [`dispatch-cleanup.sh`](bin/dispatch-cleanup.sh) |

## The number everything depends on

An instance runs a fixed number of scheduled searches at once. Everything
here is measured against it, and it is **read from the scheduler's own log**
rather than computed from the CPU count, because the computed figure is
frequently not the one being enforced:

```
concurrency_limit=4
```

Forty searches on one cron against four slots is not a tuning problem. It is
thirty-six searches waiting, every cycle, for as long as the app is
installed.

## Why "just set allow_skew" does not work

This is the trap, and it is worth stating plainly because both settings look
like the answer.

`allow_skew` and `schedule_window` let the scheduler move a search off its
scheduled minute. That genuinely spreads the load. Neither stops Splunk
reporting the run as **delayed**, because a run is late relative to the time
it was scheduled for, and deferring it does not change that time. An instance
whose searches all share a cron will keep reporting almost every run as
delayed no matter which of the two is set.

`allow_skew` has a second limitation: it applies only to `*` and `*/N` crons.
On `0 * * * *` it is silently doing nothing at all.

What works is giving the searches different minutes, which is what
[`search-stagger.py`](bin/search-stagger.py) does: a `*/15` becomes
`3,18,33,48` for one search and `4,19,34,49` for the next. The interval is
unchanged; only the offset moves. Changes are written to the app's `local/`,
so `default/` is untouched and the app can still be upgraded.

## Window against interval

A scheduled search looks back over a window, and runs on an interval. The two
should match.

| | what happens |
|---|---|
| window **wider** than the interval | each run re-reads what the last one already matched. For a search that writes to a summary index, that is the same row recorded twice |
| window **narrower** than the interval | the time between them is never examined, and a detection in that gap is never made |
| window **equal** to the interval | contiguous |

The exception is `realtime_schedule = 0`, continuous scheduling, which
anchors each run's time range to its scheduled time rather than to when it
actually started. With that set, a late run still covers the window it was
meant to, so the window can equal the interval and a deferral costs nothing.
That is why continuous scheduling and a window equal to the interval belong
together, and why a summary-indexing search without it is a search that
silently drops data whenever it gets held back.

`search-lint.py` checks all of this per search and names the file to change.

## What lint checks

| check | why it matters |
|---|---|
| collision | more searches on one minute than the instance can run. Credited if most of them may be deferred |
| window vs interval | re-reads, or gaps, as above |
| `schedule_window` >= interval | a deferred run can collide with the next scheduled one |
| `allow_skew` with no effect | set on a cron it does not apply to |
| summary index + real-time schedule | a skipped window is data never written |
| writes to a missing index | the results go nowhere, and nothing says so |
| no dispatch window | the search runs over all time, every time |
| priority inflation | when everything is `highest`, nothing is |

It exits non-zero when it finds errors, so it can gate a deployment.

## Reading one search

```bash
./bin/search-inventory.py --container splunk --name "Sigma Engine - Linux linux high 01 of 01"
```

Gives its definition, where it is defined, its schedule and window with the
interval comparison spelled out, the SPL, and what the scheduler has recently
done with it: how often it ran, how long it took, how many rows it returned
and how late it started. That last table answers most questions about a
search without opening Splunk.

## Search artifacts

Every run leaves its results under `var/run/splunk/dispatch`. Splunk reaps
them on each search's own ttl, but a reap that falls behind leaves a
directory with hundreds of thousands of entries, and the instance slows down
for a reason nothing reports, because the reason is the filesystem.

```bash
./bin/dispatch-cleanup.sh --container splunk                      # report
./bin/dispatch-cleanup.sh --container splunk --older-than 7 --delete
```

It groups usage by app, decoding the base64 in each job directory's name, so
the output names the app responsible rather than a hash. It leaves a running
job's artifact alone, and says so. If the directory fills up again, the ttl
is the thing to change, not this script.

## Common flags

| flag | |
|---|---|
| `--container NAME` | run against a container with `podman exec` |
| `--splunk-home PATH` | run against a local installation (default `/opt/splunk`) |
| `--user NAME` | override the resolved service account |
| `--app NAME` | limit to one app; repeatable on most tools |
| `--slots N` | override the concurrency limit instead of reading it |

Splunk's own apps are excluded by default, since their scheduling is not
yours to fix; `--include-splunk-apps` puts them back.

## Credentials

None of these need any. They read the merged configuration through `btool`
and the scheduler's own log, both of which are on disk. That is deliberate:
the moment you most need to know why searches are not running is not a good
moment to be looking for a password.

## Related

[`../index_maintenance`](../index_maintenance) covers the data side: what is
in each index, whether it is still arriving, moving it between indexes, and
retention.
