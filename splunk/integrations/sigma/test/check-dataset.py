#!/usr/bin/env python3

"""Check a generated dataset against the ground truth written beside it.

A round's recall and precision are only worth as much as the labels they are
scored against. This checks the dataset itself, before any of it reaches
Splunk, for the ways a generator can produce data that disagrees with its own
record of what it produced:

  future-dated events    Splunk re-times anything past MAX_DAYS_HENCE to its
                         ingest time. An event dated weeks ahead therefore
                         lands in the engine's live window whatever its
                         recorded timestamp, and a round can score a
                         detection the engine would not have made on
                         correctly dated data.
  events outside the
  declared window        the dataset says it covers N hours. An event outside
                         that is one no search aimed at the window will see.
  an instance whose
  window misses its own
  events                 a scorer matches a detection to the instance whose
                         window contains it. A window that stops short of its
                         own campaign makes a real detection read as a miss.
  counts that disagree   if planted_records does not match the instances, the
                         ground truth has lost track of what it planted.

Each check is reported separately and the exit status is non-zero if any
failed, so this can gate a round rather than be read afterwards.

Standard library only.

    ./test/check-dataset.py --dataset ./out
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# How each source type carries its event time. A dataset whose source types
# are not listed here is reported rather than passed: an unchecked file is
# not a checked one.
WIN_XML = re.compile(r'SystemTime="([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+)Z?"')
AUDITD = re.compile(r"audit\((\d+)\.\d+:")
SYSLOG_ISO = re.compile(r"^([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+)\+00:00")
HIST_EPOCH = re.compile(r"^#(\d+)$")


def event_time(sourcetype: str, line: str) -> Optional[datetime]:
    """The event's own timestamp, or None if this line does not carry one.

    A bash_history file alternates a '#epoch' line with its command, so only
    half its lines are timestamped; that is the file's shape, not a fault.
    """
    if sourcetype.startswith("XmlWinEventLog") or sourcetype == "sysmon:linux":
        m = WIN_XML.search(line)
        if m:
            return datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
        return None
    if sourcetype == "linux_audit":
        m = AUDITD.search(line)
        if m:
            return datetime.fromtimestamp(int(m.group(1)), timezone.utc)
        return None
    if sourcetype == "linux_secure":
        m = SYSLOG_ISO.match(line)
        if m:
            return datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
        return None
    if sourcetype == "bash_history":
        m = HIST_EPOCH.match(line.strip())
        if m:
            return datetime.fromtimestamp(int(m.group(1)), timezone.utc)
        return None
    return None


def load(dataset: Path) -> Tuple[Dict, Dict[str, List[str]]]:
    truth = json.loads((dataset / "ground-truth.json").read_text(encoding="utf-8"))
    lines: Dict[str, List[str]] = {}
    for sourcetype, name in truth["files"].items():
        f = dataset / name
        if not f.exists():
            continue
        lines[sourcetype] = [
            l for l in f.read_text(encoding="utf-8", errors="replace").splitlines() if l
        ]
    return truth, lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dataset", required=True, help="Directory from scenario.py")
    ap.add_argument(
        "--tolerance-seconds",
        type=int,
        default=120,
        help="Slack on the window bounds, for the time generation takes",
    )
    args = ap.parse_args(argv)

    dataset = Path(args.dataset)
    gt = dataset / "ground-truth.json"
    if not gt.exists():
        print(f"FAIL: no ground-truth.json in {dataset}")
        return 2

    truth, lines = load(dataset)
    generated = datetime.fromisoformat(truth["generated_at"])
    window = timedelta(hours=float(truth["window_hours"]))
    slack = timedelta(seconds=args.tolerance_seconds)
    earliest_allowed = generated - window - slack
    latest_allowed = generated + slack

    total = sum(len(v) for v in lines.values())
    print()
    print(f"  dataset    {dataset}")
    print(f"  generated  {generated.isoformat(timespec='seconds')}")
    print(f"  window     {truth['window_hours']:g}h")
    print(f"  records    {total:,} across {len(lines)} source type(s)")

    failures: List[str] = []

    # ---- 1. nothing dated ahead of the run ---------------------------------
    future: Dict[str, List[datetime]] = {}
    outside: Dict[str, List[datetime]] = {}
    untimed: Dict[str, int] = {}
    unknown: List[str] = []
    for sourcetype, ls in lines.items():
        if not any(event_time(sourcetype, l) for l in ls[:50]):
            unknown.append(sourcetype)
            continue
        for line in ls:
            t = event_time(sourcetype, line)
            if t is None:
                untimed[sourcetype] = untimed.get(sourcetype, 0) + 1
                continue
            if t > latest_allowed:
                future.setdefault(sourcetype, []).append(t)
            elif t < earliest_allowed:
                outside.setdefault(sourcetype, []).append(t)

    print()
    print("  === 1. no event is dated ahead of the run ===")
    if future:
        n = sum(len(v) for v in future.values())
        print(f"    FAIL: {n} event(s) dated after {generated.isoformat(timespec='seconds')}")
        for st, times in sorted(future.items()):
            times.sort()
            print(f"      {st}: {len(times)}, up to "
                  f"{times[-1].isoformat(timespec='seconds')} "
                  f"({(times[-1] - generated).days}d ahead)")
        print("      Splunk re-times these to their ingest time, so they land in")
        print("      the engine's live window whatever the recorded timestamp.")
        failures.append("future-dated events")
    else:
        print("    PASS: nothing dated ahead of the run")

    # ---- 2. everything inside the declared window --------------------------
    print()
    print("  === 2. every event is inside the declared window ===")
    if outside:
        n = sum(len(v) for v in outside.values())
        print(f"    FAIL: {n} event(s) before "
              f"{earliest_allowed.isoformat(timespec='seconds')}")
        for st, times in sorted(outside.items()):
            times.sort()
            print(f"      {st}: {len(times)}, earliest "
                  f"{times[0].isoformat(timespec='seconds')}")
        failures.append("events outside the window")
    else:
        print(f"    PASS: all timestamps within the {truth['window_hours']:g}h window")

    # ---- 3. each instance's window covers its own events -------------------
    # Attribution is exact: the ground truth records a sha1 prefix per planted
    # event, so each line is matched to the instance that produced it.
    print()
    print("  === 3. each instance's window covers the events it planted ===")
    by_digest: Dict[str, int] = {}
    for idx, inst in enumerate(truth.get("instances", [])):
        for d in inst.get("event_sha1", []):
            by_digest[d] = idx
    found: Dict[int, List[datetime]] = {}
    for sourcetype, ls in lines.items():
        for line in ls:
            d = hashlib.sha1(line.encode()).hexdigest()[:16]
            idx = by_digest.get(d)
            if idx is None:
                continue
            t = event_time(sourcetype, line)
            if t is not None:
                found.setdefault(idx, []).append(t)

    bad_window = 0
    unmatched = 0
    for idx, inst in enumerate(truth.get("instances", [])):
        times = found.get(idx)
        if not times:
            unmatched += 1
            continue
        start = datetime.fromisoformat(inst["window_start"]) - slack
        end = datetime.fromisoformat(inst["window_end"]) + slack
        stray = [t for t in times if t < start or t > end]
        if stray:
            bad_window += 1
            stray.sort()
            over = max((t - end for t in stray if t > end), default=timedelta(0))
            print(f"    FAIL: {inst['scenario']} -- {len(stray)} of {len(times)} "
                  f"event(s) outside its own window")
            print(f"      window {inst['window_start'][:19]} .. {inst['window_end'][:19]}")
            if over > timedelta(0):
                print(f"      latest event runs {over.days}d past window_end")
            print("      A scorer matching a detection to the instance whose window")
            print("      contains it will read these as belonging to nothing.")
    if bad_window:
        failures.append("instance windows that miss their own events")
    elif not truth.get("instances"):
        print("    SKIP: no instances planted")
    else:
        print(f"    PASS: all {len(truth['instances'])} instance window(s) cover "
              f"their events")
    if unmatched:
        print(f"    note: {unmatched} instance(s) had no event matched by digest; "
              f"their lines may carry a run-time tag")

    # ---- 4. the counts agree ----------------------------------------------
    print()
    print("  === 4. the ground truth counts match the files ===")
    claimed = int(truth.get("total_records", -1))
    planted_claimed = int(truth.get("planted_records", -1))
    planted_actual = sum(int(i.get("events", 0)) for i in truth.get("instances", []))
    ok = True
    if claimed != total:
        print(f"    FAIL: ground truth says {claimed:,} records, the files hold {total:,}")
        ok = False
    if planted_claimed != planted_actual:
        print(f"    FAIL: planted_records is {planted_claimed:,}, the instances "
              f"sum to {planted_actual:,}")
        ok = False
    if ok:
        print(f"    PASS: {total:,} records, {planted_actual:,} planted")
    else:
        failures.append("counts that disagree")

    if unknown:
        print()
        print(f"  note: no timestamp pattern for {', '.join(sorted(unknown))} -- "
              f"these were not time-checked")

    print()
    if failures:
        print(f"  FAIL: {', '.join(failures)}")
        print("  Do not score a round against this dataset.")
        print()
        return 1
    print("  PASS: the dataset agrees with its own ground truth")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
