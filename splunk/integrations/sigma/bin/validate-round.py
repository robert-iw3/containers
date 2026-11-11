#!/usr/bin/env python3
"""Run one labelled batch through a live instance and measure what it caught.

bin/synthesize.py produces events that a named rule provably matches, with
an independent evaluator agreeing before anything is claimed. This puts
such a batch into Splunk and compares what came back.

Two numbers decide whether an app is worth deploying, and only one of them
is usually quoted:

  recall      of the activity that was planted, how much was detected.
              A low recall means an intrusion goes unseen.
  precision   of the detections produced, how many were the planted
              activity rather than the ordinary background around it.
              A low precision means an analyst spends the week on noise
              and stops reading the queue -- which costs more than the
              missed detection, because it is permanent.

Precision is measured against background events generated alongside the
planted ones. Anything detected that was not planted is counted against it.

    ./bin/validate-round.py --batch round-t1.json --container epo-uat-indexer
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent.parent

READOUT_APP = "sigma_validation"
READOUT = """[default]
enableSched = 1
realtime_schedule = 0
schedule_priority = highest
cron_schedule = */2 * * * *
dispatch.earliest_time = -24h
dispatch.latest_time = now
counttype = number of events
relation = greater than
quantity = 0
alert.track = 0

[validation_readout]
search = index=sigma_alerts | eval first=round(sigma_first_seen,0) \
| stats count as detections, sum(sigma_match_count) as events, \
        min(first) as first_seen by sigma_rule_id, sigma_rule, sigma_src_host, sigma_level \
| outputcsv validation_readout
"""


def sh(cmd: List[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def podman(container: str, user: str, *args: str) -> str:
    return sh(["podman", "exec", "-u", user, container, *args])


def install_readout(container: str) -> None:
    """A scheduled search that writes detections where they can be read.

    The instance has no credentials available to this harness, so results
    are read from a file the scheduler writes rather than from a search.
    """
    base = f"/opt/splunk/etc/apps/{READOUT_APP}"
    existing = podman(container, "splunk", "sh", "-c",
                      f"test -f {base}/default/savedsearches.conf && echo yes || echo no")
    if existing == "yes":
        return
    podman(container, "splunk", "sh", "-c", f"mkdir -p {base}/default")
    podman(container, "splunk", "sh", "-c",
           f"printf '[install]\\nstate = enabled\\n[ui]\\nis_visible = 0\\n' > {base}/default/app.conf")
    tmp = Path("/tmp/_readout.conf")
    tmp.write_text(READOUT)
    sh(["podman", "cp", str(tmp), f"{container}:{base}/default/savedsearches.conf"])
    sh(["podman", "exec", "-u", "root", container, "chown", "-R", "splunk:splunk", base])
    print("  installed the readout search; restarting splunkd")
    podman(container, "splunk", "sh", "-c",
           "/opt/splunk/bin/splunk restart >/dev/null 2>&1")


def stage(uf: str, batch: Path, tag: str, host: str) -> None:
    """Put the batch where the forwarder will read it as new data.

    The input sets host explicitly so every event, and therefore every
    detection, carries this round's label.
    """
    lab = "/opt/splunkforwarder/etc/apps/sigma_lab_inputs/lab-logs"
    d = f"{lab}/validate/{tag}"
    sh(["podman", "exec", "-u", "root", uf, "sh", "-c",
        f"mkdir -p {d} && chown -R ansible:ansible {lab}/validate"])

    inputs = ""
    for src, st in ((batch.with_suffix(".windows.log"), "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational"),
                    (batch.with_suffix(".linux.log"), "linux_audit")):
        if not src.exists() or not src.stat().st_size:
            continue
        sh(["podman", "cp", str(src), f"{uf}:{d}/{src.name}"])
        inputs += (f"\n[monitor://{d}/{src.name}]\nsourcetype = {st}\n"
                   f"index = linux_lab\nhost = {host}\n"
                   f"disabled = 0\ncrcSalt = <SOURCE>\n")
    tmp = Path("/tmp/_validate_inputs.conf")
    tmp.write_text(inputs)
    sh(["podman", "cp", str(tmp), f"{uf}:/tmp/_v.conf"])
    sh(["podman", "exec", "-u", "root", uf, "sh", "-c",
        "cat /tmp/_v.conf >> /opt/splunkforwarder/etc/apps/sigma_lab_inputs/local/inputs.conf && "
        "chown ansible:ansible /opt/splunkforwarder/etc/apps/sigma_lab_inputs/local/inputs.conf"])
    sh(["podman", "exec", "-u", "root", uf, "chown", "-R", "ansible:ansible", d])
    podman(uf, "ansible", "sh", "-c",
           "/opt/splunkforwarder/bin/splunk restart >/dev/null 2>&1")


def batches_for(planted: Dict[str, Dict], lookup: Path) -> set:
    """The searches that carry the planted rules.

    Recall is only measurable once the search that could find a rule has
    actually run. Waiting a fixed time instead measures the scheduler's
    luck: with allow_skew spreading dozens of searches across an interval,
    a batch can start nearly ten minutes late, and a round that gave up
    first records a miss for a rule the engine detects perfectly well.
    """
    want = set()
    if not lookup.exists():
        return want
    import csv as _c
    with open(lookup, newline="", encoding="utf-8") as fh:
        for row in _c.DictReader(fh):
            if row.get("sigma_rule_id") in planted and row.get("sigma_batch"):
                want.add(row["sigma_batch"])
    return want


def ran_since(container: str, names: set, since: float) -> set:
    """Which of those searches have completed a run since the batch landed."""
    if not names:
        return set()
    log = podman(container, "splunk", "sh", "-c",
                 "grep -h 'status=success' /opt/splunk/var/log/splunk/scheduler.log "
                 "2>/dev/null | tail -4000")
    done = set()
    for line in log.splitlines():
        m = re.search(r'savedsearch_name="([^"]+)".*?dispatch_time=(\d+)', line)
        if m and m.group(1) in names and int(m.group(2)) >= since:
            done.add(m.group(1))
    return done


def read_detections(container: str) -> List[Dict[str, str]]:
    raw = podman(container, "splunk", "sh", "-c",
                 "cat /opt/splunk/var/run/splunk/csv/validation_readout.csv 2>/dev/null")
    if not raw:
        return []
    import csv as _csv
    import io
    return list(_csv.DictReader(io.StringIO(raw)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--container", default="epo-uat-indexer")
    ap.add_argument("--uf", default="epo-uat-uf")
    ap.add_argument("--wait", type=int, default=600,
                    help="seconds to wait for the engine to run")
    ap.add_argument("--no-stage", action="store_true",
                    help="read results for a batch already ingested")
    ap.add_argument("--out", default=None, help="write the result as JSON")
    ap.add_argument("--keep-readout", action="store_true",
                    help="leave the readout search installed between rounds")
    args = ap.parse_args(argv)

    batch = Path(args.batch)
    spec = json.loads(batch.read_text())
    planted = {p["rule_id"]: p for p in spec["planted"] if p["rule_id"]}
    # Derived from when the batch was generated, so no two stagings ever
    # share a label: not the control and the tier whose profile it borrows,
    # and not two runs that happened to use the same seed.
    run_id = hashlib.sha1(
        f"{spec['generated']}|{spec['tier']}|{spec['seed']}".encode()
    ).hexdigest()[:6]
    tag = f"{spec['tier']}-{spec['seed']}-{run_id}"
    host_tag = f"lab-{tag}"

    print(f"\n  Round {tag}: {len(planted)} planted rule(s), "
          f"{spec['windows_events']} Windows and {spec['linux_events']} Linux events")
    print(f"  events labelled host={host_tag}, so nothing from another round counts")

    install_readout(args.container)

    # A detection belongs to this batch if it was first seen inside the
    # window the batch was generated for, with a little slack either side
    # for scheduling.
    def in_window(row) -> bool:
        return (row.get("sigma_src_host") or "") == host_tag

    if not args.no_stage:
        print("  staging the batch")
        stage(args.uf, batch, tag, host_tag)

    # Wait for the searches that could find these rules to have run, not
    # for a clock. A fixed timeout measures scheduling luck.
    need = batches_for(planted, HERE / "app/sigma_detection_lab/lookups/sigma_rules.csv")
    staged_at = time.time()
    deadline = time.time() + args.wait
    found: Dict[str, Dict] = {}
    ran: set = set()
    while time.time() < deadline:
        rows = read_detections(args.container)
        found = {d["sigma_rule_id"]: d for d in rows if in_window(d)}
        hit = set(found) & set(planted)
        ran = ran_since(args.container, need, staged_at)
        if len(hit) >= len(planted):
            break
        if need and ran >= need:
            # Every search that could find a planted rule has now run; what
            # is missing is genuinely missing.
            break
        time.sleep(20)
    if need and not (ran >= need):
        print(f"\n  INCOMPLETE: {len(need) - len(ran)} of {len(need)} search(es) "
              f"carrying a planted rule had not run when the wait expired.")
        print(f"  Recall below is a lower bound, not a measurement. Raise --wait.")

    hit = sorted(set(found) & set(planted))
    missed = sorted(set(planted) - set(found))
    unplanted = sorted(set(found) - set(planted))

    recall = len(hit) / len(planted) * 100 if planted else 0.0
    precision = len(hit) / len(found) * 100 if found else 0.0

    print(f"\n  {'KPI':34} {'value':>10}")
    print(f"  {'-' * 46}")
    print(f"  {'planted rules':34} {len(planted):>10}")
    print(f"  {'detected':34} {len(hit):>10}")
    print(f"  {'missed':34} {len(missed):>10}")
    print(f"  {'detections not planted':34} {len(unplanted):>10}")
    print(f"  {'recall':34} {recall:>9.1f}%")
    print(f"  {'precision':34} {precision:>9.1f}%")

    if hit:
        print(f"\n  detected:")
        for rid in hit:
            print(f"    {planted[rid]['rule'][:62]}")
    if missed:
        print(f"\n  MISSED -- these were planted and provably match:")
        for rid in missed:
            p = planted[rid]
            print(f"    {p['rule'][:56]:58} {p['level']:9} {p['platform']}")
            print(f"      id {rid}")
    if unplanted:
        print(f"\n  fired on background activity -- this is what wastes an analyst's time:")
        for rid in unplanted[:10]:
            print(f"    {found[rid].get('sigma_rule', rid)[:62]}")

    result = {
        "tier": spec["tier"], "seed": spec["seed"],
        "searches_expected": len(need), "searches_ran": len(ran),
        "complete": bool(need) and ran >= need,
        "planted": len(planted), "detected": len(hit), "missed": len(missed),
        "unplanted": len(unplanted),
        "recall_pct": round(recall, 1), "precision_pct": round(precision, 1),
        "missed_rules": [{"id": r, "rule": planted[r]["rule"],
                          "level": planted[r]["level"],
                          "platform": planted[r]["platform"]} for r in missed],
        "unplanted_rules": [found[r].get("sigma_rule", r) for r in unplanted],
    }
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2))
        print(f"\n  {args.out}")
    if not args.keep_readout:
        podman(args.container, "splunk", "sh", "-c",
               "rm -rf /opt/splunk/etc/apps/%s" % READOUT_APP)
    print()
    return 0 if not missed else 1


if __name__ == "__main__":
    sys.exit(main())
