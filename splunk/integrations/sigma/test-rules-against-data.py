#!/usr/bin/env python3

"""Test converted Sigma rules against real indexed data and explain the misses.

A rule returning nothing is the normal case and says little on its own. The
useful question is why, and there are three different answers:

  NO_SOURCETYPE   the source type the rule needs is not in the index at all
  NO_FIELD        the source type is there, but the field the rule keys on
                  never appears in it
  NO_MATCH        source type and fields are both present, so the activity
                  genuinely did not happen

Only NO_MATCH means the detection is sound and waiting. NO_SOURCETYPE is a
collection gap. NO_FIELD is usually a parsing or conversion problem and is
the one worth fixing first.

Rules are converted with pySigma and run through the Splunk CLI, so no REST
credentials or HEC token are needed beyond a search login.

  SPLUNK_PASSWORD=... ./test-rules-against-data.py \
      --rules ./rules --index linux_lab --pipeline pipelines/splunk-linux.yml
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:
    from sigma.collection import SigmaCollection
    from sigma.backends.splunk import SplunkBackend
    from sigma.processing.pipeline import ProcessingPipeline
    from sigma.pipelines.splunk import splunk_cim_data_model, splunk_windows_pipeline
except ImportError:
    sys.exit("pySigma is required: python3 -m pip install --target ./pylib "
             "-r requirements.txt   (then set PYTHONPATH=./pylib)")

BUILTIN = {
    "none": None,
    "cim": splunk_cim_data_model,
    "windows": splunk_windows_pipeline,
}


def build_backend(spec):
    if not spec or spec == "none":
        return SplunkBackend()
    if spec in BUILTIN:
        return SplunkBackend(processing_pipeline=BUILTIN[spec]())
    path = Path(spec)
    if not path.is_absolute() and (HERE / spec).exists():
        path = HERE / spec
    if not path.exists():
        raise SystemExit(f"pipeline not found: {spec}")
    return SplunkBackend(
        processing_pipeline=ProcessingPipeline.from_yaml(path.read_text(encoding="utf-8")))


class Splunk:
    """Runs searches through the CLI inside the container."""

    def __init__(self, container, user, password, splunk_home):
        self.container = container
        self.user = user
        self.password = password
        self.bin = f"{splunk_home}/bin/splunk"

    def search(self, spl, earliest="-10y", latest="now", maxout=5, timeout=180):
        """Run one search. Returns (rows, error).

        The CLI's own 'search' subcommand already implies a leading search
        command, so a query starting with 'search ' double-prefixes and
        silently returns nothing. Any leading one is stripped here.
        """
        query = spl.strip()
        if query.lower().startswith("search "):
            query = query[7:]
        cmd = [
            "podman", "exec", "-u", "splunk", self.container, self.bin, "search", query,
            "-earliest_time", earliest, "-latest_time", latest,
            "-maxout", str(maxout), "-output", "json", "-preview", "false",
            "-auth", f"{self.user}:{self.password}",
        ]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return [], "timeout"
        out, err = p.stdout, p.stderr
        # A certificate warning on stderr is noise, not failure.
        err_lines = [l for l in err.splitlines()
                     if l.strip() and "Server Certificate Hostname Validation" not in l
                     and not l.startswith("WARNING")]
        if p.returncode != 0 or (err_lines and not out.strip()):
            return [], "; ".join(err_lines)[:300] or f"exit {p.returncode}"
        rows = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "result" in obj:
                rows.append(obj["result"])
            elif isinstance(obj, list):
                rows.extend(obj)
        return rows, ""


def spl_sourcetypes(spl):
    return set(re.findall(r'sourcetype\s*=\s*"?([A-Za-z0-9_:\-./]+)"?', spl))


def spl_fields(spl):
    """Field names the query filters on, excluding Splunk's own metadata."""
    skip = {"index", "sourcetype", "source", "host", "earliest", "latest",
            "eventtype", "tag", "_time", "_raw", "splunk_server"}
    found = set()
    for m in re.finditer(r'(?<![\w.])([A-Za-z_][A-Za-z0-9_.]{1,40})\s*(?:=|IN\s*\()', spl):
        name = m.group(1)
        if name.lower() in skip:
            continue
        if name.startswith(("eval", "stats", "where", "regex", "rex", "search")):
            continue
        found.add(name)
    return found


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rules", required=True, help="Sigma rules directory")
    ap.add_argument("--index", required=True, help="Index holding the test data")
    ap.add_argument("--pipeline", default="pipelines/splunk-linux.yml")
    ap.add_argument("--container", default="epo-uat-indexer")
    ap.add_argument("--splunk-home", default="/opt/splunk")
    ap.add_argument("--user", default=os.environ.get("SPLUNK_USER", "admin"))
    ap.add_argument("--earliest", default="-10y",
                    help="Staged historical logs can be months old, so the "
                         "default window is deliberately wide")
    ap.add_argument("--limit", type=int, default=0, help="Test only the first N rules")
    ap.add_argument("--out", default=None, help="Write a JSON report here")
    args = ap.parse_args(argv[1:])

    password = os.environ.get("SPLUNK_PASSWORD")
    if not password:
        sys.exit("set SPLUNK_PASSWORD in the environment")

    splunk = Splunk(args.container, args.user, password, args.splunk_home)

    # What is actually in the index? Establish this once, not per rule.
    print(f"Profiling index={args.index} ...")
    rows, err = splunk.search(
        f"index={args.index} | stats count by sourcetype", maxout=200)
    if err:
        sys.exit(f"could not profile the index: {err}")
    present = {r["sourcetype"]: int(r["count"]) for r in rows if "sourcetype" in r}
    if not present:
        sys.exit(f"index={args.index} holds no events; nothing to test against")
    print(f"{'sourcetype':<44} {'events':>12}")
    for st, n in sorted(present.items(), key=lambda x: -x[1]):
        print(f"{st:<44} {n:>12,}")

    # Which fields exist per sourcetype, so a miss can be explained.
    fields_by_st = {}
    for st in present:
        rows, err = splunk.search(
            f'index={args.index} sourcetype="{st}" | fieldsummary maxvals=0 '
            f'| fields field', maxout=500)
        fields_by_st[st] = {r["field"] for r in rows if "field" in r} if not err else set()
        print(f"  {st}: {len(fields_by_st[st])} extracted fields")

    rules_dir = Path(args.rules)
    files = sorted(rules_dir.rglob("*.yml"))
    if args.limit:
        files = files[:args.limit]
    print(f"\nConverting and testing {len(files)} rules ...\n")

    verdicts = Counter()
    results = []
    for i, f in enumerate(files, 1):
        rel = str(f.relative_to(rules_dir))
        try:
            coll = SigmaCollection.load_ruleset([str(f)])
            spl = str(build_backend(args.pipeline).convert(coll)[0]).strip()
            spl = re.sub(r"\s*\n\s*", " ", spl)
        except Exception as e:
            verdicts["CONVERT_FAIL"] += 1
            results.append({"rule": rel, "verdict": "CONVERT_FAIL",
                            "detail": f"{type(e).__name__}: {str(e)[:160]}"})
            continue

        need_st = spl_sourcetypes(spl)
        missing_st = {s for s in need_st if s not in present}
        if missing_st:
            verdicts["NO_SOURCETYPE"] += 1
            results.append({"rule": rel, "verdict": "NO_SOURCETYPE", "spl": spl,
                            "detail": f"not in index: {sorted(missing_st)}"})
            continue

        scope_st = need_st or set(present)
        need_fields = spl_fields(spl)
        have = set()
        for st in scope_st:
            have |= fields_by_st.get(st, set())
        missing_fields = {x for x in need_fields if x not in have}
        # A field absent from every candidate source type cannot ever match.
        if missing_fields and len(missing_fields) == len(need_fields) and need_fields:
            verdicts["NO_FIELD"] += 1
            results.append({"rule": rel, "verdict": "NO_FIELD", "spl": spl,
                            "detail": f"never extracted: {sorted(missing_fields)}"})
            continue

        query = f"index={args.index} {spl}"
        rows, err = splunk.search(query, earliest=args.earliest, maxout=5)
        if err:
            verdicts["DISPATCH_ERROR"] += 1
            results.append({"rule": rel, "verdict": "DISPATCH_ERROR", "spl": spl,
                            "detail": err})
        elif rows:
            verdicts["FIRED"] += 1
            results.append({"rule": rel, "verdict": "FIRED", "spl": spl,
                            "hits": len(rows),
                            "detail": f"{len(rows)} result(s), capped at 5"})
        else:
            verdicts["NO_MATCH"] += 1
            results.append({"rule": rel, "verdict": "NO_MATCH", "spl": spl,
                            "detail": "source type and fields present; "
                                      "activity did not occur",
                            "partial_missing_fields": sorted(missing_fields)})
        if i % 25 == 0:
            print(f"  {i}/{len(files)} ... {dict(verdicts)}")

    print("\n================ RESULT ================")
    order = ["FIRED", "NO_MATCH", "NO_FIELD", "NO_SOURCETYPE",
             "DISPATCH_ERROR", "CONVERT_FAIL"]
    total = sum(verdicts.values())
    for k in order:
        if verdicts[k]:
            print(f"  {verdicts[k]:>5}  {k:<16} {verdicts[k]/total*100:>5.1f}%")
    print(f"  {total:>5}  total")

    fired = [r for r in results if r["verdict"] == "FIRED"]
    if fired:
        print("\nRules that fired on real data:")
        for r in sorted(fired, key=lambda x: -x.get("hits", 0)):
            print(f"  [{r.get('hits')}] {r['rule']}")
            print(f"        {r['spl'][:150]}")

    for label, head in (("NO_FIELD", "Fields never extracted (parsing or conversion)"),
                        ("DISPATCH_ERROR", "Searches that failed to dispatch")):
        sel = [r for r in results if r["verdict"] == label]
        if sel:
            print(f"\n{head}: {len(sel)}")
            agg = Counter(r["detail"] for r in sel)
            for d, n in agg.most_common(8):
                print(f"  {n:>4}x {d[:140]}")

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"index": args.index, "sourcetypes_present": present,
             "verdicts": dict(verdicts), "results": results}, indent=1),
            encoding="utf-8")
        print(f"\nreport: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
