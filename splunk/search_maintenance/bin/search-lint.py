#!/usr/bin/env python3

"""Check every scheduled search against the ways scheduling goes wrong.

Static: it reads the merged configuration and never runs a search. Each
finding names the search, the file it is defined in, and what to change.

The checks are the faults that are expensive precisely because nothing
reports them. A search that errors is obvious. A search that quietly reads
the wrong window, or that is scheduled on the same minute as fifty others,
runs green forever and is wrong the whole time.

  collision        more searches fire on one minute than the instance can
                   run at once, so they queue. Every one is then reported
                   as delayed, and whatever else is scheduled waits behind
                   them.
  window vs period a window wider than the interval re-reads events the
                   last run already matched, and writes the same summary
                   row twice. Narrower leaves a gap, unless continuous
                   scheduling is on, which closes it by anchoring each run
                   to its scheduled time.
  schedule_window  must be below the interval, or a deferred run collides
                   with the next scheduled one.
  allow_skew       applies only to */N and * crons. On any other cron it
                   is silently doing nothing.
  summary + rt     real-time scheduling skips a window it could not run.
                   For a search that writes to a summary index, a skipped
                   window is data that will never be written.
  dead write       a summary index the instance does not define.
  no window        a scheduled search with no dispatch range searches all
                   time, every run.

    ./bin/search-lint.py --container splunk
    ./bin/search-lint.py --container splunk --app sigma_detection_lab
    ./bin/search-lint.py --splunk-home /opt/splunk --quiet
"""
from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import splunkenv as E  # noqa: E402

FINDINGS = []


def finding(level: str, check: str, search: str, app: str, detail: str,
            fix: str = "") -> None:
    FINDINGS.append({"level": level, "check": check, "search": search,
                     "app": app, "detail": detail, "fix": fix})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--container")
    ap.add_argument("--splunk-home", default="/opt/splunk")
    ap.add_argument("--user")
    ap.add_argument("--app", action="append", default=[],
                    help="Limit to these apps; repeatable")
    ap.add_argument("--include-splunk-apps", action="store_true",
                    help="Also check the apps that ship with Splunk")
    ap.add_argument("--slots", type=int, default=None,
                    help="Scheduled search concurrency; read from the "
                         "instance when not given")
    ap.add_argument("--quiet", action="store_true",
                    help="Only print findings, not the summary tables")
    args = ap.parse_args(argv)

    t = E.Target(args.container, args.splunk_home, args.user)
    slots = args.slots or E.concurrency_limit(t) or 4
    searches = E.saved_searches(t)

    SPLUNK_OWN = ("splunk_", "Splunk_", "search", "learned", "introspection",
                  "alert_", "legacy", "sample_app", "journald_input",
                  "python_upgrade", "appsbrowser", "user-prefs", "audit_trail",
                  "SplunkDeploymentServerConfig", "SplunkForwarder",
                  "SplunkLightForwarder")
    if args.app:
        searches = [s for s in searches if s.app in args.app]
    elif not args.include_splunk_apps:
        searches = [s for s in searches
                    if not s.app.startswith(SPLUNK_OWN) and s.app != "system"]

    sched = [s for s in searches if s.scheduled]

    print()
    print(f"  {len(searches)} saved search(es), {len(sched)} scheduled")
    print(f"  the instance runs {slots} scheduled search(es) at once")
    if args.app:
        print(f"  limited to: {', '.join(args.app)}")
    elif not args.include_splunk_apps:
        print("  Splunk's own apps are excluded; --include-splunk-apps adds them")

    # ---- when does everything fire ------------------------------------
    by_minute = collections.defaultdict(list)
    unparsed = []
    for s in sched:
        mins = E.cron_minutes(s.cron)
        if mins is None:
            unparsed.append(s)
            continue
        for m in mins:
            by_minute[m].append(s)

    if not args.quiet and by_minute:
        print()
        print("  === how many searches fire on each minute of the hour ===")
        worst = sorted(by_minute.items(), key=lambda kv: -len(kv[1]))[:12]
        for minute, group in sorted(worst, key=lambda kv: kv[0]):
            bar = "#" * min(len(group), 60)
            flag = "  <-- over the limit" if len(group) > slots else ""
            print(f"    :{minute:02d}  {len(group):>4}  {bar}{flag}")

    for minute, group in sorted(by_minute.items()):
        if len(group) <= slots:
            continue
        apps = collections.Counter(s.app for s in group)
        worst_app = apps.most_common(1)[0]
        # A search the scheduler is allowed to move is not really competing
        # for that one minute. Credit it, because telling someone to fix
        # something they already handled is how a checker gets ignored.
        movable = sum(1 for s in group
                      if s.get("schedule_window") or s.get("allow_skew"))
        share = movable / len(group)
        if share >= 0.8:
            finding("WARN", "collision, spread allowed",
                    f"{len(group)} searches", worst_app[0],
                    f"all scheduled on minute :{minute:02d} against {slots} "
                    f"slots, but {movable} of them may be deferred, so the "
                    f"scheduler spreads them itself. Mostly "
                    f"{worst_app[0]} ({worst_app[1]}).",
                    "Nothing to do unless they are still arriving late; "
                    "bin/scheduler-health.py reports whether they are.")
        else:
            finding("ERROR", "collision",
                    f"{len(group)} searches", worst_app[0],
                    f"all fire on minute :{minute:02d}, and only {slots} can "
                    f"run at once, and {len(group) - movable} of them may not "
                    f"be deferred. Mostly {worst_app[0]} ({worst_app[1]}).",
                    "Spread them across minutes with "
                    "bin/search-stagger.py, or set schedule_window so the "
                    "scheduler may move them.")

    # ---- per search ----------------------------------------------------
    indexes = set()
    for line in t.splunk("btool indexes list").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            indexes.add(line[1:-1])

    for s in sched:
        period = E.cron_period_minutes(s.cron)
        window = E.window_minutes(s.get("dispatch.earliest_time"))
        continuous = s.get("realtime_schedule", "1").lower() in ("0", "false")
        summary = s.summary_index

        if not s.cron:
            finding("ERROR", "no cron", s.name, s.app,
                    "scheduled but has no cron_schedule.",
                    "Give it a cron_schedule, or turn enableSched off.")

        if s.get("dispatch.earliest_time", "") == "" and s.cron:
            finding("ERROR", "no window", s.name, s.app,
                    "no dispatch.earliest_time, so every run searches all "
                    "time.",
                    "Set dispatch.earliest_time to the interval it runs on.")

        if period and window:
            if window > period * 1.01:
                finding("WARN", "window > period", s.name, s.app,
                        f"looks back {window:g}m but runs every {period:g}m, "
                        f"so each run re-reads {window - period:g}m the last "
                        f"one already saw."
                        + (f" It writes to {summary}, so that is the same row "
                           f"recorded twice." if summary else ""),
                        "Make the window equal the interval.")
            elif window < period * 0.99 and not continuous:
                finding("ERROR", "window < period", s.name, s.app,
                        f"looks back {window:g}m but runs every {period:g}m, "
                        f"leaving {period - window:g}m unexamined between "
                        f"runs.",
                        "Widen the window to the interval, or set "
                        "realtime_schedule = 0 so the scheduler anchors each "
                        "run to its scheduled time.")

        sw = s.get("schedule_window", "")
        if sw and sw != "auto":
            try:
                swv = int(sw)
            except ValueError:
                swv = None
            if swv is not None and period and swv >= period:
                finding("WARN", "schedule_window >= period", s.name, s.app,
                        f"may be deferred by {swv}m but runs every {period:g}m, "
                        f"so a deferred run can collide with the next.",
                        "Keep schedule_window below the interval.")

        skew = s.get("allow_skew", "")
        if skew and s.cron:
            minute = s.cron.split()[0] if s.cron.split() else ""
            if not (minute == "*" or minute.startswith("*/")):
                finding("WARN", "allow_skew has no effect", s.name, s.app,
                        f"allow_skew = {skew} is set, but it applies only to "
                        f"* and */N crons and this is '{s.cron}'.",
                        "Use schedule_window, which works on any cron and is "
                        "not counted as a delayed search.")

        if summary and not continuous:
            finding("ERROR", "summary with real-time schedule", s.name, s.app,
                    f"writes to {summary} but realtime_schedule is on, so a "
                    f"window it could not run is dropped rather than caught "
                    f"up. For a summary index that is data never written.",
                    "Set realtime_schedule = 0.")

        if summary and summary not in indexes:
            finding("ERROR", "writes to a missing index", s.name, s.app,
                    f"writes to '{summary}', which this instance does not "
                    f"define. The results go nowhere.",
                    f"Create {summary}, or point the action at an index that "
                    f"exists.")

        if s.get("dispatch.latest_time", "") == "" and s.get("dispatch.earliest_time"):
            finding("WARN", "no latest_time", s.name, s.app,
                    "has an earliest but no dispatch.latest_time.",
                    "Set dispatch.latest_time, usually to now.")

    prio = collections.Counter(s.get("schedule_priority", "default")
                               for s in sched)
    if prio.get("highest", 0) > slots:
        finding("WARN", "priority inflation", f"{prio['highest']} searches", "-",
                f"{prio['highest']} searches claim schedule_priority = "
                f"highest, which is more than the {slots} that can run at "
                f"once. When everything is highest, nothing is.",
                "Reserve highest for the few that genuinely cannot wait.")

    for s in unparsed:
        finding("WARN", "cron not understood", s.name, s.app,
                f"cron_schedule '{s.cron}' could not be read, so this search "
                f"was left out of the collision check.", "")

    # ---- report --------------------------------------------------------
    errors = [f for f in FINDINGS if f["level"] == "ERROR"]
    warns = [f for f in FINDINGS if f["level"] == "WARN"]
    print()
    if not FINDINGS:
        print("  PASS: nothing to report across "
              f"{len(sched)} scheduled search(es)")
        print()
        return 0

    for level, group in (("ERROR", errors), ("WARN", warns)):
        if not group:
            continue
        print(f"  === {level}: {len(group)} ===")
        by_check = collections.defaultdict(list)
        for f in group:
            by_check[f["check"]].append(f)
        for check, items in by_check.items():
            print()
            print(f"  {check}  ({len(items)})")
            for f in items[:8]:
                print(f"    {f['app']}/{f['search']}")
                print(f"      {f['detail']}")
                if f["fix"]:
                    print(f"      -> {f['fix']}")
            if len(items) > 8:
                print(f"    ... and {len(items) - 8} more")
        print()

    print(f"  {len(errors)} error(s), {len(warns)} warning(s)")
    print()
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
