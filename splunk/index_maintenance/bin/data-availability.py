#!/usr/bin/env python3

"""Is the data still arriving, and from where?

The failure that costs the most is not a broken search -- it is a source
that stopped reporting and nobody noticed. The index is still there, the
dashboards still draw, and the events simply stop. A detection that cannot
see a host is indistinguishable from a host doing nothing wrong.

This reports, for every index, every source type and host in it, how many
events there are, when the last one arrived, and how long it has been
quiet. Anything past the quiet threshold is called out, and anything past
the silent threshold makes the exit status non-zero so this can be run as
a check rather than read as a page.

It works from the metadata Splunk maintains in each bucket, so it needs no
credentials. With credentials (--auth-file, or it asks) it also reports what
arrived in the last hour, which the metadata cannot distinguish from what
arrived yesterday when a bucket spans both.

    ./bin/data-availability.py --container splunk
    ./bin/data-availability.py --container splunk --by host --quiet-after 2
    ./bin/data-availability.py --container splunk --index linux_lab --json out.json
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import splunkmeta as M  # noqa: E402


def ago(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 0:
        return "in the future"
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60}m"
    if seconds < 172800:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--container")
    ap.add_argument("--splunk-home", default="/opt/splunk")
    ap.add_argument("--user")
    ap.add_argument("--index", action="append", default=[],
                    help="Limit to these indexes; repeatable")
    ap.add_argument("--by", default="sourcetype",
                    choices=("sourcetype", "host", "source"),
                    help="What to break each index down by")
    ap.add_argument("--quiet-after", type=float, default=24,
                    help="Hours of no new events before a source is called quiet")
    ap.add_argument("--silent-after", type=float, default=72,
                    help="Hours before it is called silent, and the exit status fails")
    ap.add_argument("--include-internal", action="store_true",
                    help="Include Splunk's own _* indexes")
    ap.add_argument("--auth-file", help="First line is user:password")
    ap.add_argument("--ask-auth", action="store_true",
                    help="Ask for credentials, for the recent-arrivals column")
    ap.add_argument("--json", dest="json_out", help="Write the full result here")
    args = ap.parse_args(argv)

    t = M.Target(args.container, args.splunk_home, args.user)
    auth = None
    if args.auth_file:
        auth = Path(args.auth_file).read_text().splitlines()[0].strip()
    elif os.environ.get("SPLUNK_AUTH"):
        auth = os.environ["SPLUNK_AUTH"]
    elif args.ask_auth:
        if not sys.stdin.isatty():
            print("FAIL: --ask-auth needs a terminal", file=sys.stderr)
            return 2
        u = input("  Splunk username: ").strip()
        p = getpass.getpass(f"  Password for {u}: ")
        if u and p:
            auth = f"{u}:{p}"

    names = args.index or M.indexes(t)
    if not args.include_internal and not args.index:
        names = [n for n in names if not n.startswith("_")]

    now = time.time()
    quiet_s = args.quiet_after * 3600
    silent_s = args.silent_after * 3600

    print()
    print(f"  {t.home}{f'  in {args.container}' if args.container else ''}")
    print(f"  broken down by {args.by}; quiet after {args.quiet_after:g}h, "
          f"silent after {args.silent_after:g}h")
    print(f"  as at {time.strftime('%F %T', time.gmtime(now))} UTC")

    result = {"generated": now, "by": args.by, "indexes": {}}
    worst = "ok"
    empty, rows_total = [], 0

    for idx in names:
        settings = M.index_settings(t, idx)
        md = M.metadata(t, idx, settings, args.by)
        if not md:
            empty.append(idx)
            result["indexes"][idx] = {"events": 0, "rows": []}
            continue
        print()
        total = sum(r.count for r in md.values())
        print(f"  == {idx} -- {total:,} event(s) across {len(md)} {args.by}(s) ==")
        print(f"    {'value':34} {'events':>11}  {'last event':19} {'quiet':>7}  state")
        print(f"    {'-' * 86}")
        rows = []
        for r in sorted(md.values(), key=lambda r: -(r.latest or 0)):
            gap = now - (r.latest or 0)
            if gap > silent_s:
                state = "SILENT"
                worst = "silent"
            elif gap > quiet_s:
                state = "quiet"
                if worst == "ok":
                    worst = "quiet"
            else:
                state = "ok"
            last = (time.strftime("%F %T", time.gmtime(r.latest))
                    if r.latest else "never")
            print(f"    {r.value[:34]:34} {r.count:>11,}  {last:19} "
                  f"{ago(gap):>7}  {state}")
            rows.append({"value": r.value, "events": r.count,
                         "first_event": r.earliest, "last_event": r.latest,
                         "quiet_seconds": int(gap), "state": state})
            rows_total += 1
        result["indexes"][idx] = {"events": total, "rows": rows}

        # The metadata says when the newest event in a bucket is, not how
        # many arrived recently. A bucket spanning two days reports the same
        # latest whether one event or a million came in today.
        if auth:
            out = t.sh(
                f"IM_A='{auth}' sh -c '{t.home}/bin/splunk search "
                f"\"| tstats count where index={idx} earliest=-1h by {args.by}\" "
                f"-output csv -preview false -auth \"$IM_A\"' 2>/dev/null")
            recent = {}
            for line in out.splitlines()[1:]:
                parts = [c.strip('"') for c in line.split(",")]
                if len(parts) >= 2 and parts[-1].isdigit():
                    recent[parts[0]] = int(parts[-1])
            if recent:
                print(f"    in the last hour: " +
                      ", ".join(f"{k} {v:,}" for k, v in
                                sorted(recent.items(), key=lambda x: -x[1])[:6]))
            else:
                print("    in the last hour: nothing")

    if empty:
        print()
        print(f"  == holding no data: {len(empty)} index(es) ==")
        for idx in empty:
            print(f"    {idx}")
        print("    An index with no data is not necessarily wrong -- it may be")
        print("    new, or for data that has not arrived yet. It is wrong if")
        print("    something is configured to write to it.")

    print()
    print(f"  {rows_total} {args.by}(s) across {len(names) - len(empty)} "
          f"index(es) holding data")
    if worst == "silent":
        print(f"  FAIL: at least one source has sent nothing for "
              f"{args.silent_after:g}h")
    elif worst == "quiet":
        print(f"  WARN: at least one source has sent nothing for "
              f"{args.quiet_after:g}h")
    else:
        print("  PASS: every source has reported recently")
    print()

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2))
        print(f"  {args.json_out}")
        print()
    return 1 if worst == "silent" else 0


if __name__ == "__main__":
    sys.exit(main())
