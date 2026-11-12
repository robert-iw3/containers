#!/usr/bin/env python3

"""What the scheduler has actually been doing, as opposed to what the
configuration says it should.

bin/search-lint.py reads the configuration and predicts trouble. This reads
scheduler.log and reports what happened: what ran, what was held back, how
late things started, and which searches are consuming the instance.

The number that governs everything here is how many scheduled searches may
run at once. It is read from the scheduler's own log rather than computed
from the CPU count, because the computed figure is frequently not the one
being enforced.

A search held back is logged as 'continued', with a reason. That is not an
error and Splunk will run it later, but a queue that never drains means
every detection arrives late, and a detection that arrives late enough is
the same as one that did not arrive.

    ./bin/scheduler-health.py --container splunk
    ./bin/scheduler-health.py --container splunk --app sigma_detection_lab
    ./bin/scheduler-health.py --container splunk --lines 50000
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import splunkenv as E  # noqa: E402

VERDICTS = []


def verdict(state: str, name: str, detail: str = "") -> None:
    VERDICTS.append(state)
    print(f"  {state:5} {name:32} {detail}")


def pct(a: int, b: int) -> float:
    return (a * 100.0 / b) if b else 0.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--container")
    ap.add_argument("--splunk-home", default="/opt/splunk")
    ap.add_argument("--user")
    ap.add_argument("--app", action="append", default=[])
    ap.add_argument("--lines", type=int, default=20000,
                    help="How much of scheduler.log to read")
    ap.add_argument("--delayed-warn", type=float, default=10,
                    help="Percent of runs held back before warning")
    ap.add_argument("--lag-warn", type=int, default=120,
                    help="Seconds between schedule and start before warning")
    args = ap.parse_args(argv)

    t = E.Target(args.container, args.splunk_home, args.user)
    slots = E.concurrency_limit(t)
    runs = E.scheduler_runs(t, args.lines)
    if args.app:
        runs = [r for r in runs if r.app in args.app]

    print()
    print(f"  {t.home}{f'  in {args.container}' if args.container else ''}")
    print(f"  {len(runs)} scheduler entries read")
    print(f"  concurrency limit: {slots if slots else 'not stated in the log'}"
          "  (read from the scheduler, not computed)")
    print()

    if not runs:
        print("  nothing in scheduler.log to report on.")
        print()
        return 0

    status = collections.Counter(r.status for r in runs if r.status)
    ran = status.get("success", 0)
    held = status.get("continued", 0)
    skipped = status.get("skipped", 0)
    total = ran + held + skipped

    # ---- was anything held back ----------------------------------------
    held_pct = pct(held, total)
    detail = f"{held} of {total} runs held back ({held_pct:.0f}%)"
    if skipped:
        detail += f", {skipped} skipped outright"
    if skipped:
        verdict("FAIL", "searches held back", detail
                + " -- a skipped run is one that will not be caught up")
    elif held_pct >= args.delayed_warn:
        verdict("WARN", "searches held back", detail)
    else:
        verdict("PASS", "searches held back", detail)

    reasons = collections.Counter(r.reason for r in runs
                                  if r.status == "continued" and r.reason)
    for reason, n in reasons.most_common(3):
        print(f"        {n:>6}  {reason[:88]}")

    # ---- how late did things start -------------------------------------
    skews = sorted(r.skew for r in runs if r.skew is not None)
    if skews:
        mid = skews[len(skews) // 2]
        p90 = skews[int(len(skews) * 0.9)]
        worst = skews[-1]
        d = f"median {mid}s, 90th {p90}s, worst {worst}s"
        if worst >= args.lag_warn * 4:
            verdict("FAIL", "how late runs started", d)
        elif p90 >= args.lag_warn:
            verdict("WARN", "how late runs started", d)
        else:
            verdict("PASS", "how late runs started", d)
        print("        a deferral the scheduler was told it may make is not a")
        print("        fault; schedule_window is how you grant that")
    else:
        verdict("WARN", "how late runs started", "no skew recorded")

    # ---- who is using the instance --------------------------------------
    cost = collections.defaultdict(float)
    counts = collections.Counter()
    for r in runs:
        if r.run_time:
            cost[(r.app, r.name)] += r.run_time
            counts[(r.app, r.name)] += 1
    if cost:
        print()
        print("  === which searches cost the most, over the entries read ===")
        print(f"    {'app / search':62} {'runs':>6} {'total s':>9} {'avg s':>7}")
        for (app, name), secs in sorted(cost.items(), key=lambda kv: -kv[1])[:10]:
            n = counts[(app, name)]
            label = f"{app}/{name}"
            print(f"    {label[:62]:62} {n:>6} {secs:>9.1f} {secs / n:>7.2f}")

    # ---- searches that run and find nothing, every time -----------------
    outcome = collections.defaultdict(lambda: [0, 0])
    for r in runs:
        if r.status != "success" or r.results is None:
            continue
        key = (r.app, r.name)
        outcome[key][0] += 1
        if r.results > 0:
            outcome[key][1] += 1
    silent = [(k, v[0]) for k, v in outcome.items() if v[0] >= 5 and v[1] == 0]
    if silent:
        print()
        print(f"  === {len(silent)} search(es) ran at least 5 times and never "
              f"returned a row ===")
        for (app, name), n in sorted(silent, key=lambda kv: -kv[1])[:10]:
            print(f"    {app}/{name}"[:78] + f"  ({n} runs)")
        print("    That is correct for a detection with nothing to detect. It")
        print("    is also what a broken search looks like, so it is worth")
        print("    knowing which of yours are in this list.")

    # ---- errors ----------------------------------------------------------
    failed = [r for r in runs if r.status and r.status not in
              ("success", "continued", "skipped")]
    if failed:
        verdict("FAIL", "runs that did not complete", f"{len(failed)}")
        for r in failed[:5]:
            print(f"        {r.app}/{r.name}  status={r.status}")
    else:
        verdict("PASS", "runs that did not complete", "none")

    fails = VERDICTS.count("FAIL")
    warns = VERDICTS.count("WARN")
    print()
    print(f"  {len(VERDICTS)} check(s): {fails} FAIL, {warns} WARN, "
          f"{len(VERDICTS) - fails - warns} PASS")
    if fails:
        print("  FAIL")
    elif warns:
        print("  WARN")
    else:
        print("  PASS")
    print()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
