#!/usr/bin/env python3

"""Spread scheduled searches across minutes so they stop queueing.

An app that schedules forty searches on `*/15 * * * *` fires all forty on
the same minute. An instance runs a handful at once, so the rest queue, each
one starts further from its schedule than the last, and Splunk reports
almost every run as delayed.

Deferral settings do not fix this. allow_skew and schedule_window both let
the scheduler move a search, which spreads the load, but the run is still
counted against its original schedule: a search deferred by five minutes is
still a search that started five minutes late, and the health report says
so. The fix is to schedule them on different minutes in the first place.

This rewrites the cron of each search so that a `*/15` becomes `3,18,33,48`
for one search, `4,19,34,49` for the next, and so on. Every search keeps its
interval exactly; only its offset within that interval changes.

Nothing is written without --apply. Changes go to the app's
local/savedsearches.conf, which overrides default/ without editing it, so
the app can still be upgraded.

    ./bin/search-stagger.py --container splunk --app sigma_detection_lab
    ./bin/search-stagger.py --container splunk --app sigma_detection_lab --apply
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import splunkenv as E  # noqa: E402


def staggered_cron(period: int, offset: int) -> str:
    """A cron with the same interval, started `offset` minutes later."""
    if period >= 1440:
        return ""                      # daily or rarer: leave it alone
    if period >= 60:
        hours = period // 60
        hour_field = "*" if hours == 1 else f"*/{hours}"
        return f"{offset % 60} {hour_field} * * *"
    minutes = sorted((offset % period) + k * period
                     for k in range(60 // period))
    return ",".join(str(m) for m in minutes) + " * * * *"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--container")
    ap.add_argument("--splunk-home", default="/opt/splunk")
    ap.add_argument("--user")
    ap.add_argument("--app", required=True,
                    help="The app whose searches to spread")
    ap.add_argument("--slots", type=int, default=None,
                    help="Scheduled search concurrency; read from the "
                         "instance when not given")
    ap.add_argument("--apply", action="store_true",
                    help="Write the new crons to the app's local/")
    ap.add_argument("--restart", action="store_true",
                    help="Restart splunkd afterwards so they take effect")
    args = ap.parse_args(argv)

    t = E.Target(args.container, args.splunk_home, args.user)
    slots = args.slots or E.concurrency_limit(t) or 4
    searches = [s for s in E.saved_searches(t)
                if s.app == args.app and s.scheduled]
    if not searches:
        print(f"\n  no scheduled searches in '{args.app}'\n")
        return 2

    print()
    print(f"  {args.app}: {len(searches)} scheduled search(es)")
    print(f"  the instance runs {slots} at once")

    # Group by interval: searches that run every 15 minutes are spread over
    # those 15 minutes, hourly ones over the hour.
    by_period = collections.defaultdict(list)
    skipped = []
    for s in sorted(searches, key=lambda s: s.name):
        period = E.cron_period_minutes(s.cron)
        if not period or period >= 1440:
            skipped.append(s)
            continue
        by_period[period].append(s)

    print()
    print(f"  {'search':54} {'now':>18}  {'becomes':>18}")
    print(f"  {'-' * 96}")
    plan = []
    for period, group in sorted(by_period.items()):
        per_minute = max(1, (len(group) + period - 1) // period)
        if per_minute > slots:
            print(f"  NOTE: {len(group)} search(es) every {period}m is "
                  f"{per_minute} per minute, above the {slots} that can run "
                  f"at once.")
            print(f"        They will still queue. Lengthen the interval, or "
                  f"batch the searches.")
        for i, s in enumerate(group):
            new = staggered_cron(period, i % period)
            if not new or new == s.cron:
                continue
            plan.append((s, new))
            print(f"  {s.name[:54]:54} {s.cron:>18}  {new[:18]:>18}")

    for s in skipped:
        print(f"  {s.name[:54]:54} {s.cron:>18}  {'left alone':>18}")

    if not plan:
        print()
        print("  nothing to change.")
        print()
        return 0

    # How the load looks afterwards.
    after = collections.Counter()
    for s, new in plan:
        for m in (E.cron_minutes(new) or []):
            after[m] += 1
    worst = max(after.values()) if after else 0
    print()
    print(f"  busiest minute afterwards: {worst} search(es) against "
          f"{slots} slot(s)")

    if not args.apply:
        print()
        print("  This was a plan. Re-run with --apply to write it.")
        print()
        return 0

    # Written to local/, which overrides default/ without editing it.
    local = f"{t.home}/etc/apps/{args.app}/local/savedsearches.conf"
    existing = t.sh(f"cat '{local}' 2>/dev/null")
    import re
    blocks = {}
    for b in re.split(r"(?m)^(?=\[)", existing):
        if b.strip().startswith("["):
            blocks[b.split("]")[0].lstrip("[")] = b
    for s, new in plan:
        b = blocks.get(s.name, f"[{s.name}]\n")
        if re.search(r"(?m)^cron_schedule\s*=", b):
            b = re.sub(r"(?m)^cron_schedule\s*=.*$",
                       f"cron_schedule = {new}", b)
        else:
            b = b.rstrip("\n") + f"\ncron_schedule = {new}\n"
        blocks[s.name] = b
    out = "\n".join(v.rstrip("\n") for v in blocks.values()) + "\n"

    tmp = Path("/tmp/_stagger.conf")
    tmp.write_text(out)
    t.sh(f"mkdir -p '{t.home}/etc/apps/{args.app}/local'")
    import subprocess
    if args.container:
        subprocess.run(["podman", "cp", str(tmp),
                        f"{args.container}:{local}"], capture_output=True)
        subprocess.run(["podman", "exec", "-u", "root", args.container,
                        "chown", f"{t.user}:{t.user}", local],
                       capture_output=True)
    else:
        Path(local).write_text(out)
    print()
    print(f"  written to {local}")
    if args.restart:
        print("  restarting splunkd")
        t.sh(f"{t.home}/bin/splunk restart >/dev/null 2>&1")
    else:
        print("  not in force until splunkd restarts, or the configuration "
              "is reloaded")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
