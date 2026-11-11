#!/usr/bin/env python3

"""Is this instance healthy, and will it still be accepting data tomorrow?

Each check prints PASS, WARN or FAIL with the reading behind it, so a result
can be argued with rather than just believed. The exit status is non-zero if
anything FAILed, which makes this usable as a check and not only as a page
to read.

The checks, in the order they matter for staying up:

  free disk        below server.conf's minFreeSpace, indexing stops. Not
                   slows -- stops. This is the most common way a working
                   instance becomes a broken one.
  index caps       an index at its maxTotalDataSizeMB is already deleting
                   its oldest data to make room, whatever its retention says.
  blocked queues   a blocked queue means data arriving faster than it can be
                   processed. Sustained, the forwarders stop sending.
  licence          going over the daily volume repeatedly ends in a warning
                   and then in searches being disabled.
  forwarders       which are connected, and on what version.
  errors           what splunkd has been complaining about.
  data currency    whether anything has stopped arriving.

It needs no credentials: everything here is on disk or in Splunk's own logs.

    ./bin/health-check.py --container splunk
    ./bin/health-check.py --container splunk --quiet-after 2
"""
from __future__ import annotations

import argparse
import collections
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import splunkmeta as M  # noqa: E402

VERDICTS = []


def verdict(state: str, name: str, detail: str = "") -> None:
    VERDICTS.append((state, name))
    print(f"  {state:5} {name:34} {detail}")


def human_kb(kb: int) -> str:
    if kb >= 1048576:
        return f"{kb / 1048576:.1f}G"
    if kb >= 1024:
        return f"{kb / 1024:.0f}M"
    return f"{kb}K"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--container")
    ap.add_argument("--splunk-home", default="/opt/splunk")
    ap.add_argument("--user")
    ap.add_argument("--quiet-after", type=float, default=24,
                    help="Hours before a source with no new events is reported")
    ap.add_argument("--cap-warn", type=float, default=85,
                    help="Percent of an index's size cap that triggers a warning")
    ap.add_argument("--licence-warn", "--license-warn", type=float, default=85,
                    dest="licence_warn",
                    help="Percent of the licence quota that triggers a warning")
    args = ap.parse_args(argv)

    t = M.Target(args.container, args.splunk_home, args.user)
    now = time.time()

    print()
    print(f"  {t.home}{f'  in {args.container}' if args.container else ''}")
    print(f"  as at {time.strftime('%F %T', time.gmtime(now))} UTC")
    print()

    # ---- splunkd -------------------------------------------------------
    status = t.splunk("status")
    if "is running" in status:
        pid = re.search(r"pid (\d+)", status)
        verdict("PASS", "splunkd", f"running{f', pid {pid.group(1)}' if pid else ''}")
    else:
        verdict("FAIL", "splunkd", "not running -- nothing below will be current")

    # ---- free disk vs minFreeSpace -------------------------------------
    # Splunk stops indexing when the filesystem holding an index falls below
    # minFreeSpace, so this is measured against that figure rather than a
    # round percentage.
    mfs = 5000
    for line in t.splunk("btool server list diskUsage").splitlines():
        if "minFreeSpace" in line and "=" in line:
            v = line.split("=", 1)[1].strip()
            if v.isdigit():
                mfs = int(v)
    names = [n for n in M.indexes(t)]
    vols = {}
    for idx in names:
        s = M.index_settings(t, idx)
        home, _ = M.index_dirs(t, idx, s)
        if home:
            vols.setdefault(home.rsplit("/", 2)[0], idx)
    for vol, example in sorted(vols.items()):
        used, avail, pct = M.disk_free(t, vol)
        if avail == 0 and used == 0:
            verdict("WARN", f"disk {vol[:24]}", "could not read df")
            continue
        avail_mb = avail // 1024
        detail = (f"{human_kb(avail)} free ({100 - pct}%), "
                  f"minFreeSpace is {mfs}M")
        if avail_mb < mfs:
            verdict("FAIL", f"disk {vol[:24]}",
                    detail + " -- indexing has stopped or will")
        elif avail_mb < mfs * 2:
            verdict("WARN", f"disk {vol[:24]}",
                    detail + " -- within twice the floor")
        else:
            verdict("PASS", f"disk {vol[:24]}", detail)

    # ---- index size caps ----------------------------------------------
    over = []
    for idx in names:
        s = M.index_settings(t, idx)
        cap_mb = s.get("maxTotalDataSizeMB", "")
        cap_mb = int(cap_mb) if cap_mb.isdigit() else 0
        if cap_mb <= 0:
            continue
        home, cold = M.index_dirs(t, idx, s)
        base = home[:-3] if home.endswith("/db") else home
        kb = M.du_kb(t, base)
        if kb == 0:
            continue
        pct = kb * 100 / (cap_mb * 1024)
        if pct >= args.cap_warn:
            over.append((idx, pct, kb, cap_mb))
    if over:
        for idx, pct, kb, cap_mb in sorted(over, key=lambda x: -x[1]):
            verdict("WARN" if pct < 100 else "FAIL", f"cap {idx[:28]}",
                    f"{pct:.0f}% of {cap_mb}M used -- oldest data is being "
                    f"dropped to make room" if pct >= 100 else
                    f"{pct:.0f}% of {cap_mb}M used")
    else:
        verdict("PASS", "index size caps", f"none above {args.cap_warn:g}%")

    # ---- blocked queues ------------------------------------------------
    # Only the most recent reading per queue counts: a block an hour ago that
    # cleared is history, and reporting it as current would be wrong.
    qlog = t.sh(f"grep -h 'group=queue' {t.home}/var/log/splunk/metrics.log "
                f"2>/dev/null | tail -400")
    latest = {}
    for line in qlog.splitlines():
        m = re.search(r"name=(\w+)", line)
        cur = re.search(r"current_size_kb=(\d+)", line)
        mx = re.search(r"max_size_kb=(\d+)", line)
        b = re.search(r"blocked_count=(\d+)", line)
        if m and cur and mx:
            latest[m.group(1)] = (int(cur.group(1)), int(mx.group(1)),
                                  int(b.group(1)) if b else 0)
    blocked = {k: v for k, v in latest.items() if v[2] > 0 or (v[1] and v[0] >= v[1])}
    if not latest:
        verdict("WARN", "processing queues", "no queue metrics found")
    elif blocked:
        for k, (cur, mx, bc) in sorted(blocked.items()):
            verdict("FAIL", f"queue {k[:28]}",
                    f"{cur}/{mx} KB, blocked {bc} time(s) in the last reading")
    else:
        fullest = max(latest.items(), key=lambda kv: (kv[1][0] / kv[1][1]) if kv[1][1] else 0)
        k, (cur, mx, _) = fullest
        verdict("PASS", "processing queues",
                f"{len(latest)} queue(s), fullest is {k} at {cur}/{mx} KB")

    # ---- licence volume ------------------------------------------------
    # The quota, the licence type and what happens when the quota is passed
    # all differ between licences, and a trial's 500 MB says nothing about
    # any other installation. So the stack, the pool and the quota are all
    # read from this instance, and the threshold is the caller's to set.
    today = time.strftime("%m-%d-%Y", time.gmtime(now))
    stacks = [x for x in t.sh(
        f"ls {t.home}/etc/licenses 2>/dev/null").split() if x]
    manager = "self"
    for line in t.splunk("btool server list license").splitlines():
        if line.strip().startswith("manager_uri") and "=" in line:
            manager = line.split("=", 1)[1].strip()
    lic = t.sh(f"grep -h 'type=Usage' {t.home}/var/log/splunk/license_usage.log "
               f"2>/dev/null | grep '^{today}'")
    total_b, poolsz = 0, 0
    pools = set()
    for line in lic.splitlines():
        b = re.search(r"\bb=(\d+)", line)
        ps = re.search(r"poolsz=(\d+)", line)
        pl = re.search(r'pool="([^"]*)"', line)
        if b:
            total_b += int(b.group(1))
        if ps:
            poolsz = max(poolsz, int(ps.group(1)))
        if pl:
            pools.add(pl.group(1))
    where = "this instance is its own licence manager" if manager == "self" \
        else f"the quota is held by the licence manager at {manager}"
    if poolsz:
        pct = total_b * 100 / poolsz
        verdict("FAIL" if pct >= 100 else
                "WARN" if pct >= args.licence_warn else "PASS",
                "licence volume",
                f"{total_b / 1048576:.0f}M of {poolsz / 1048576:.0f}M "
                f"today ({pct:.0f}%), warn at {args.licence_warn:g}%")
    elif total_b:
        verdict("PASS", "licence volume",
                f"{total_b / 1048576:.0f}M today; no pool quota reported")
    else:
        verdict("WARN", "licence volume", "no usage recorded today")
    print(f"        stack{'s' if len(stacks) != 1 else ''}: "
          f"{', '.join(stacks) or 'none found in etc/licenses'}")
    if pools:
        print(f"        pool{'s' if len(pools) != 1 else ''}: "
              f"{', '.join(sorted(pools))}")
    print(f"        {where}")

    # ---- forwarders ----------------------------------------------------
    fwd = t.sh(f"grep -h 'group=tcpin_connections' "
               f"{t.home}/var/log/splunk/metrics.log 2>/dev/null | tail -200")
    seen = {}
    for line in fwd.splitlines():
        h = re.search(r"hostname=([^\s,]+)", line)
        v = re.search(r"version=([^\s,]+)", line)
        g = re.search(r"guid=([^\s,]+)", line)
        if h:
            seen[h.group(1)] = (v.group(1) if v else "?",
                                g.group(1)[:8] if g else "?")
    if seen:
        verdict("PASS", "forwarders connected", f"{len(seen)}")
        for h, (v, g) in sorted(seen.items()):
            print(f"        {h:30} version {v:10} guid {g}")
    else:
        verdict("WARN", "forwarders connected",
                "none in the recent metrics -- data may arrive another way")

    # ---- recent errors -------------------------------------------------
    err = t.sh(f"grep -h -E '^[0-9-]+ [0-9:.]+ [+-][0-9]+ (ERROR|WARN)' "
               f"{t.home}/var/log/splunk/splunkd.log 2>/dev/null | tail -500")
    kinds = collections.Counter()
    for line in err.splitlines():
        m = re.search(r"(ERROR|WARN)\s+(\w+)", line)
        if m:
            kinds[(m.group(1), m.group(2))] += 1
    errors = sum(n for (lvl, _), n in kinds.items() if lvl == "ERROR")
    if errors:
        verdict("WARN", "splunkd errors",
                f"{errors} ERROR line(s) in the last 500 logged")
        for (lvl, comp), n in kinds.most_common(6):
            if lvl == "ERROR":
                print(f"        {n:>5}  {comp}")
    else:
        verdict("PASS", "splunkd errors", "none in the last 500 logged")

    # ---- data currency -------------------------------------------------
    quiet_s = args.quiet_after * 3600
    stale, live, empty = [], 0, 0
    for idx in names:
        if idx.startswith("_"):
            continue
        s = M.index_settings(t, idx)
        md = M.metadata(t, idx, s, "sourcetype")
        if not md:
            empty += 1
            continue
        for r in md.values():
            if now - (r.latest or 0) > quiet_s:
                stale.append((idx, r.value, now - (r.latest or 0)))
            else:
                live += 1
    if stale:
        verdict("WARN", "data currency",
                f"{live} source(s) current, {len(stale)} quiet for over "
                f"{args.quiet_after:g}h")
        for idx, st, gap in sorted(stale, key=lambda x: -x[2])[:8]:
            print(f"        {idx}/{st:28} {int(gap // 3600)}h")
        print("        bin/data-availability.py reports these in full")
    else:
        verdict("PASS", "data currency",
                f"all {live} source(s) have reported in the last "
                f"{args.quiet_after:g}h")
    if empty:
        print(f"        ({empty} index(es) hold no data at all)")

    fails = sum(1 for s, _ in VERDICTS if s == "FAIL")
    warns = sum(1 for s, _ in VERDICTS if s == "WARN")
    print()
    print(f"  {len(VERDICTS)} check(s): {fails} FAIL, {warns} WARN, "
          f"{len(VERDICTS) - fails - warns} PASS")
    if fails:
        print("  FAIL -- see the failing checks above.")
    elif warns:
        print("  WARN -- nothing is down, but something needs attention.")
    else:
        print("  PASS")
    print()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
