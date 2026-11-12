#!/usr/bin/env python3

"""Every saved search on the instance, and everything about one of them.

Without --name it lists them: which app, whether it is scheduled, on what
cron, over what window, what it writes to, and which file defines it. That
last column is the one people come looking for.

With --name it gives one search in full, including what the scheduler has
actually done with it recently, which is usually how a question about a
search gets answered.

    ./bin/search-inventory.py --container splunk
    ./bin/search-inventory.py --container splunk --app sigma_detection_lab
    ./bin/search-inventory.py --container splunk --scheduled-only --csv out.csv
    ./bin/search-inventory.py --container splunk --name "Sigma Engine - Linux linux high 01 of 01"
"""
from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import splunkenv as E  # noqa: E402

SPLUNK_OWN = ("splunk_", "Splunk_", "search", "learned", "introspection",
              "alert_", "legacy", "sample_app", "journald_input",
              "python_upgrade", "appsbrowser", "user-prefs", "audit_trail",
              "SplunkDeploymentServerConfig", "SplunkForwarder",
              "SplunkLightForwarder")


def short(t: E.Target, path: str) -> str:
    return (path or "?").replace(f"{t.home}/etc/", "")


def detail(t: E.Target, s: E.SavedSearch, runs) -> None:
    print()
    print(f"  {s.app} / {s.name}")
    print(f"  {'-' * 92}")
    print(f"  defined in        {short(t, s.file)}")
    print(f"  scheduled         {'yes' if s.scheduled else 'no'}")
    for key, label in (
        ("cron_schedule", "cron"),
        ("dispatch.earliest_time", "window from"),
        ("dispatch.latest_time", "window to"),
        ("realtime_schedule", "realtime_schedule"),
        ("schedule_window", "schedule_window"),
        ("allow_skew", "allow_skew"),
        ("schedule_priority", "priority"),
        ("action.summary_index._name", "writes to"),
        ("alert.track", "tracked as an alert"),
        ("alert.severity", "severity"),
        ("counttype", "alert condition"),
        ("disabled", "disabled"),
    ):
        v = s.get(key)
        if v:
            print(f"  {label:17} {v}")

    period = E.cron_period_minutes(s.cron)
    window = E.window_minutes(s.get("dispatch.earliest_time"))
    if period and window:
        if abs(window - period) < 0.01:
            print(f"  interval vs window  every {period:g}m over {window:g}m "
                  f"-- contiguous, no overlap and no gap")
        elif window > period:
            print(f"  interval vs window  every {period:g}m over {window:g}m "
                  f"-- re-reads {window - period:g}m each run")
        else:
            cont = s.get("realtime_schedule", "1").lower() in ("0", "false")
            note = ("continuous scheduling closes it"
                    if cont else "that is a gap")
            print(f"  interval vs window  every {period:g}m over {window:g}m "
                  f"-- {note}")

    spl = s.get("search", "")
    if spl:
        print()
        print("  the search")
        for line in spl.splitlines() or [spl]:
            for i in range(0, len(line), 88):
                print(f"    {line[i:i + 88]}")

    mine = [r for r in runs if r.name == s.name]
    print()
    if not mine:
        print("  the scheduler log holds no runs of this search")
        print()
        return
    status = collections.Counter(r.status for r in mine)
    print(f"  recent runs       {len(mine)} in the log: "
          + ", ".join(f"{v} {k}" for k, v in status.most_common()))
    ok = [r for r in mine if r.status == "success"]
    if ok:
        times = [r.run_time for r in ok if r.run_time is not None]
        res = [r.results for r in ok if r.results is not None]
        if times:
            print(f"  run time          avg {sum(times) / len(times):.2f}s, "
                  f"worst {max(times):.2f}s")
        if res:
            hits = sum(1 for r in res if r > 0)
            print(f"  results           returned rows on {hits} of {len(res)} "
                  f"run(s)")
        print()
        print(f"    {'when':20} {'status':10} {'run s':>7} {'rows':>6} {'late s':>7}")
        for r in mine[-10:]:
            print(f"    {str(r.when or ''):20} {str(r.status or ''):10} "
                  f"{(f'{r.run_time:.2f}' if r.run_time is not None else ''):>7} "
                  f"{(r.results if r.results is not None else ''):>6} "
                  f"{(r.skew if r.skew is not None else ''):>7}")
    print()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--container")
    ap.add_argument("--splunk-home", default="/opt/splunk")
    ap.add_argument("--user")
    ap.add_argument("--app", action="append", default=[])
    ap.add_argument("--name", help="Show one search in full")
    ap.add_argument("--scheduled-only", action="store_true")
    ap.add_argument("--include-splunk-apps", action="store_true")
    ap.add_argument("--csv", help="Write the listing here as CSV")
    ap.add_argument("--lines", type=int, default=20000,
                    help="How much of scheduler.log to read for run history")
    args = ap.parse_args(argv)

    t = E.Target(args.container, args.splunk_home, args.user)
    searches = E.saved_searches(t)

    if args.name:
        runs = E.scheduler_runs(t, args.lines)
        hits = [s for s in searches if s.name == args.name]
        if not hits:
            near = [s for s in searches if args.name.lower() in s.name.lower()]
            print(f"\n  no search named {args.name!r}")
            if near:
                print("  did you mean:")
                for s in near[:10]:
                    print(f"    {s.app}/{s.name}")
            print()
            return 2
        for s in hits:
            detail(t, s, runs)
        return 0

    if args.app:
        searches = [s for s in searches if s.app in args.app]
    elif not args.include_splunk_apps:
        searches = [s for s in searches
                    if not s.app.startswith(SPLUNK_OWN) and s.app != "system"]
    if args.scheduled_only:
        searches = [s for s in searches if s.scheduled]

    print()
    print(f"  {len(searches)} saved search(es)")
    print()
    print(f"  {'app':22} {'search':40} {'cron':>16} {'window':>9} {'writes to':14} defined in")
    print(f"  {'-' * 140}")
    rows = []
    for s in sorted(searches, key=lambda s: (s.app, s.name)):
        cron = s.cron if s.scheduled else "(not scheduled)"
        win = s.get("dispatch.earliest_time", "")
        rows.append({
            "app": s.app, "name": s.name, "scheduled": s.scheduled,
            "cron": s.cron, "earliest": win,
            "latest": s.get("dispatch.latest_time", ""),
            "summary_index": s.summary_index,
            "priority": s.get("schedule_priority", ""),
            "schedule_window": s.get("schedule_window", ""),
            "realtime_schedule": s.get("realtime_schedule", ""),
            "file": short(t, s.file),
        })
        print(f"  {s.app[:22]:22} {s.name[:40]:40} {cron[:16]:>16} "
              f"{win[:9]:>9} {s.summary_index[:14]:14} {short(t, s.file)}")

    by_app = collections.Counter(s.app for s in searches)
    print()
    print("  by app:  " + ", ".join(f"{a} {n}" for a, n in by_app.most_common()))
    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows
                               else ["app"])
            w.writeheader()
            w.writerows(rows)
        print(f"  {args.csv}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
