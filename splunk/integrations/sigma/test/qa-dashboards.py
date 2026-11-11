#!/usr/bin/env python3
"""Run every search in every dashboard against a live instance.

A dashboard that errors shows the error in a panel and nowhere else. Nobody
reads eight dashboards' worth of panels after each change, so a broken
search survives until someone needs it -- which is the worst moment to find
out. Several defects in this integration were exactly that: a regex that
stopped matching when stanza names changed, a transpose given an empty
column name, a pivot whose time range was invalid, a panel reporting
"Running normally" when nothing had run.

This extracts the query from every panel of every view, resolves the tokens
to values a real instance will accept, schedules them all, and reports
which errored, which returned nothing, and which returned data.

A panel returning no rows is reported separately from one that errored. An
empty panel can be correct -- nothing matched in the period -- so it is a
warning to read. An error never is.

    ./bin/qa-dashboards.py --container epo-uat-indexer
    ./bin/qa-dashboards.py --container epo-uat-indexer --views alert_detail
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple

HERE = Path(__file__).resolve().parent.parent  # the integration root
APP = "sigma_qa"

# Tokens a panel expects at run time, set to values a real instance has so
# an empty result means the search found nothing rather than that the token
# was nonsense.
TOKENS: Dict[str, str] = {
    "tr.earliest": "-7d@d", "tr.latest": "now",
    "earliest": "-7d@d", "latest": "now",
    "sev_tok": "*", "plat_tok": "*", "host_tok": "*", "rule_tok": "*",
    "status_tok": 'case_status="*"', "analyst_tok": "qa",
    "scale_tok": "10", "sev": "*", "plat": "*", "disp": "*", "find": "*",
    "tac": "*", "act_tok": "note", "res_tok": "false positive",
    "text_tok": "qa", "go_tok": "record", "wrote": "",
    "rule_id": "071d5e5a-9cef-47ec-bc4e-a42e34d8d0ed", "c_id": "qa", "c_rule": "qa", "c_ruleid": "qa",
    "c_host": "qa", "c_when": "qa", "c_sev": "high", "prior_status": "open",
    "sel_rule": "Possible Coin Miner CPU Priority Param", "sel_host": "lab-t1-11", "sel_when": "qa", "sel_st": "qa",
    "sel_idx": "linux_lab", "sel_from": "-7d@d", "sel_to": "now",
    "sel_ruleid": "071d5e5a-9cef-47ec-bc4e-a42e34d8d0ed", "hostsel": "*", "rule_sel": "qa", "never": "",
}

# Panels whose purpose is to write. Running them would append to the case
# journal, so they are reported as skipped rather than exercised.
WRITES = ("| collect ", "| outputlookup", "| delete")


def sh(cmd: List[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def podman(c: str, *a: str) -> str:
    return sh(["podman", "exec", "-u", "splunk", c, *a])


def resolve(q: str) -> str:
    out = q
    for _ in range(4):
        before = out
        for name, val in TOKENS.items():
            out = out.replace("$" + name + "$", val)
        out = re.sub(r"\$([A-Za-z_][\w.]*)\|s\$",
                     lambda m: TOKENS.get(m.group(1), "qa"), out)
        out = re.sub(r"\$([A-Za-z_][\w.]*)\$",
                     lambda m: TOKENS.get(m.group(1), "*"), out)
        if out == before:
            break
    return " ".join(out.split())


def collect_queries(views: Path, only: List[str]):
    """(view, panel title, resolved search) for every panel in every view."""
    found = []
    for f in sorted(views.glob("*.xml")):
        if only and f.stem not in only:
            continue
        root = ET.parse(f).getroot()
        # A post-process panel is only runnable with its base prepended.
        bases = {}
        for s in root.iter("search"):
            sid, q = s.get("id"), s.find("query")
            if sid and q is not None and q.text:
                bases[sid] = q.text
        parent = {c: p for p in root.iter() for c in p}
        n = 0
        for s in root.iter("search"):
            q = s.find("query")
            if q is None or not q.text:
                continue
            base = s.get("base")
            if base and base not in bases:
                continue
            text = (bases[base] + "\n" + q.text) if base else q.text
            n += 1
            title = None
            node = parent.get(s)
            while node is not None and title is None:
                t = node.find("title") if hasattr(node, "find") else None
                if t is not None and t.text:
                    title = t.text
                node = parent.get(node)
            found.append((f.stem, title or ("panel %d" % n), resolve(text)))
    return found


def check_links(views: Path) -> List[str]:
    """A drilldown that sets a token the target view does not have.

    The link is accepted, the token is ignored, and the target opens
    unfiltered or with a token rendered as the literal "null". Nothing
    errors, so it survives until someone follows the pivot and finds the
    wrong thing.
    """
    inputs: Dict[str, set] = {}
    for f in views.glob("*.xml"):
        root = ET.parse(f).getroot()
        inputs[f.stem] = {i.get("token") for i in root.iter("input") if i.get("token")}
    problems = []
    for f in sorted(views.glob("*.xml")):
        body = f.read_text()
        for m in re.finditer(r'/app/[\w_]+/([\w_]+)\?([^<"]+)', body):
            target, qs = m.group(1), m.group(2).replace("&amp;", "&")
            if target not in inputs:
                problems.append("%s -> %s (no such view)" % (f.stem, target))
                continue
            for part in qs.split("&"):
                if not part.startswith("form."):
                    continue
                tok = part.split("=")[0][5:].split(".")[0]
                if tok not in inputs[target] and tok != "tr":
                    problems.append("%s -> %s sets form.%s, which %s does not have"
                                    % (f.stem, target, tok, target))
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--container", default="epo-uat-indexer")
    ap.add_argument("--views", nargs="*", default=[])
    ap.add_argument("--app", default="sigma_detection_lab")
    ap.add_argument("--wait", type=int, default=480)
    ap.add_argument("--keep", action="store_true",
                    help="leave the QA app installed for inspection; it "
                         "schedules 93 searches and will compete with the engine")
    args = ap.parse_args(argv)

    views = HERE / "app" / args.app / "default/data/ui/views"
    link_problems = check_links(views)
    if link_problems:
        print("\n  DRILLDOWN LINKS that cannot work:")
        for pb in link_problems:
            print("    " + pb)
    else:
        print("\n  drilldown links: every form token exists on its target view")
    queries = collect_queries(views, args.views)
    print("\n  %d panel search(es) across %d view(s)\n"
          % (len(queries), len({v for v, _, _ in queries})))

    conf = ["[default]", "enableSched = 1", "realtime_schedule = 0",
            "schedule_priority = highest", "cron_schedule = */3 * * * *",
            "dispatch.earliest_time = -7d@d", "dispatch.latest_time = now",
            "counttype = number of events", "relation = greater than",
            "quantity = 0", "alert.track = 0", ""]
    names, skipped = {}, []
    for i, (view, title, q) in enumerate(queries):
        if any(w in q for w in WRITES):
            skipped.append((view, title))
            continue
        nm = "qa_%03d" % i
        names[nm] = (view, title)
        # Bounded: this checks that a search runs, not what it returns.
        conf += ["[%s]" % nm, "search = %s | head 5 | outputcsv %s" % (q, nm), ""]

    tmp = Path("/tmp/_qa.conf")
    tmp.write_text("\n".join(conf))
    base = "/opt/splunk/etc/apps/%s" % APP
    podman(args.container, "sh", "-c", "mkdir -p %s/default" % base)
    podman(args.container, "sh", "-c",
           "printf '[install]\\nstate = enabled\\n[ui]\\nis_visible = 0\\n' > %s/default/app.conf" % base)
    sh(["podman", "cp", str(tmp), "%s:%s/default/savedsearches.conf" % (args.container, base)])
    sh(["podman", "exec", "-u", "root", args.container, "chown", "-R", "splunk:splunk", base])
    podman(args.container, "sh", "-c", "rm -f /opt/splunk/var/run/splunk/csv/qa_*.csv")
    print("  scheduling %d search(es); %d skipped as writes" % (len(names), len(skipped)))
    podman(args.container, "sh", "-c", "/opt/splunk/bin/splunk restart >/dev/null 2>&1")

    deadline, done = time.time() + args.wait, {}
    while time.time() < deadline and len(done) < len(names):
        log = podman(args.container, "sh", "-c",
                     "grep -h 'app=\"sigma_qa\"' /opt/splunk/var/log/splunk/scheduler.log 2>/dev/null | tail -6000")
        done = {}
        for line in log.splitlines():
            m = re.search(r'savedsearch_name="(qa_\d+)"', line)
            if not m:
                continue
            nm = m.group(1)
            if "ERROR" in line:
                em = re.search(r'message="([^"]*)"', line)
                done[nm] = "ERROR:" + (em.group(1) if em else "unknown")
            elif "status=success" in line and nm not in done:
                done[nm] = "ok"
        if len(done) >= len(names):
            break
        time.sleep(20)

    errors, empty, ok = [], [], []
    for nm, (view, title) in sorted(names.items()):
        state = done.get(nm)
        if state is None:
            errors.append((view, title, "did not run"))
        elif state.startswith("ERROR"):
            errors.append((view, title, state[6:]))
        else:
            rows = podman(args.container, "sh", "-c",
                          "cat /opt/splunk/var/run/splunk/csv/%s.csv 2>/dev/null | wc -l" % nm)
            (empty if (rows or "0").strip() in ("0", "1") else ok).append((view, title))

    if not args.keep:
        podman(args.container, "sh", "-c", "rm -rf %s" % base)
        podman(args.container, "sh", "-c",
               "/opt/splunk/bin/splunk restart >/dev/null 2>&1")
        print("  removed the QA app; it is scaffolding, not part of the install")

    print("\n  %-34s %6s" % ("result", "count"))
    print("  " + "-" * 42)
    print("  %-34s %6d" % ("returned data", len(ok)))
    print("  %-34s %6d" % ("ran, returned nothing", len(empty)))
    print("  %-34s %6d" % ("ERRORED or did not run", len(errors)))
    print("  %-34s %6d" % ("skipped (write panels)", len(skipped)))

    if errors:
        print("\n  ERRORS -- a failure visible in the dashboard:")
        for view, title, why in errors:
            print("    %-22s %-42s %s" % (view, title[:40], why[:70]))
    if empty:
        print("\n  returned no rows (may be correct -- nothing matched):")
        for view, title in empty[:24]:
            print("    %-22s %s" % (view, title[:52]))
    print()
    return 1 if (errors or link_problems) else 0


if __name__ == "__main__":
    sys.exit(main())
