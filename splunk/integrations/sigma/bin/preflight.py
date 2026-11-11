#!/usr/bin/env python3
"""Check a rule set before it is deployed, without touching Splunk.

Every failure this integration has had was visible before deployment and
was found afterwards instead, from a dashboard reading zero:

  - a rule whose match text contained a pipe produced a search with
    unbalanced parentheses, which Splunk rejected at run time, silently
    disabling every rule batched with it
  - rules keyed on fields the configured add-ons never produce, which match
    nothing and look exactly like a quiet environment
  - a schedule with more searches than the instance's concurrency allows,
    where the scheduler defers everything and never reports a failure
  - rules whose log source is not mapped, which scan the entire index

Each of those is a question that can be answered offline. This answers
them, and exits non-zero so it can gate a deployment.

    ./bin/preflight.py rules-core/.../windows/process_creation rules-core/.../linux
    ./bin/preflight.py <rules> --fields planning/available-fields.txt --slots 4

--fields takes an inventory of the fields the environment actually
produces, one per line. bin/field-inventory.sh collects it from a running
instance; without it the field check is skipped and says so, because a
check that did not run must not read as a check that passed.
"""
from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "pylib"))
sys.path.insert(0, str(HERE / "bin"))

import yaml  # noqa: E402
import sigma2splunkalert as s2s  # noqa: E402

from importlib import util as _util  # noqa: E402
_spec = _util.spec_from_file_location("build_engine", HERE / "bin" / "build-engine.py")
be = _util.module_from_spec(_spec)
_spec.loader.exec_module(be)

# Fields that come from Splunk itself rather than from an add-on, so their
# absence from an inventory is not a finding.
BUILTIN_FIELDS = {
    "index", "sourcetype", "source", "host", "_raw", "_time", "splunk_server",
    "linecount", "eventtype", "tag", "punct", "date_hour", "date_mday",
}

# A field expression in converted SPL: Name=..., Name IN (...), Name!=...
FIELD_RE = re.compile(r'(?<![\w.])([A-Za-z_][A-Za-z0-9_.]{1,48})\s*(?:!=|=|\bIN\b)')


class Result:
    def __init__(self):
        self.failures: List[str] = []
        self.warnings: List[str] = []
        self.skipped: List[str] = []

    def fail(self, msg): self.failures.append(msg)
    def warn(self, msg): self.warnings.append(msg)
    def skip(self, msg): self.skipped.append(msg)


def referenced_fields(spl: str) -> Set[str]:
    """Field names a converted rule tests, ignoring text inside strings."""
    out, buf, in_quote, i = set(), [], False, 0
    while i < len(spl):
        c = spl[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            in_quote = not in_quote
        elif not in_quote:
            buf.append(c)
        i += 1
    for m in FIELD_RE.finditer("".join(buf)):
        name = m.group(1)
        if name not in BUILTIN_FIELDS and not name.isupper():
            out.add(name)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+", help="Sigma rule folders or files")
    ap.add_argument("--config", "-c", default=str(HERE / "config.yaml"))
    ap.add_argument("--sigma-config", "-sc", default=str(HERE / "splunk-all.yml"))
    ap.add_argument("--scopes", default=str(HERE / "logsource-scope.yml"))
    ap.add_argument("--fields", default=None,
                    help="inventory of fields the environment produces")
    ap.add_argument("--slots", type=int, default=4,
                    help="concurrent scheduled searches the instance allows")
    ap.add_argument("--seconds-per-search", type=float, default=5.0,
                    help="assumed run time per batched search")
    ap.add_argument("--budget", type=int, default=20000)
    ap.add_argument("--strict", action="store_true",
                    help="treat warnings as failures")
    args = ap.parse_args(argv)

    r = Result()
    config = dict(s2s.openSigma2SplunkConfiguration(args.config))
    config["search_transformations"] = []
    config["summary_index"] = {"enabled": False}
    sigma_config = s2s.openSigmaConfiguration(args.sigma_config)

    files: List[str] = []
    for src in args.sources:
        files.extend(s2s.loadSigmaRules(src))
    print(f"\n  Rule set: {len(files)} file(s)\n")

    # ---- 1. every rule converts -------------------------------------
    rules, fail_reasons = [], collections.Counter()
    for f in files:
        try:
            doc = yaml.safe_load(Path(f).read_text(encoding="utf-8")) or {}
            product = ((doc.get("logsource") or {}).get("product") or "").lower()
        except Exception:
            product = ""
        uc, err = s2s.process_rule(
            f, "windows" if product == "windows" else "none",
            config, sigma_config, "default")
        if uc is None:
            fail_reasons[err.split(":")[0][:50]] += 1
            continue
        uc._source_path = f
        rules.append(uc)

    converted = len(rules)
    print(f"  [1] conversion      {converted}/{len(files)} converted")
    if fail_reasons:
        for reason, n in fail_reasons.most_common(5):
            print(f"                      {n:5}  {reason}")
        r.warn(f"{sum(fail_reasons.values())} rule(s) did not convert")

    # ---- 2. duplicate rule ids --------------------------------------
    ids = collections.Counter(x.rule_id for x in rules if x.rule_id)
    dupes = [i for i, n in ids.items() if n > 1]
    missing_id = sum(1 for x in rules if not x.rule_id)
    print(f"  [2] identity        {len(ids)} distinct ids, "
          f"{len(dupes)} duplicated, {missing_id} missing")
    if dupes:
        # Attribution is keyed on the id, so a duplicate makes two rules
        # indistinguishable in every detection they produce.
        r.fail(f"{len(dupes)} duplicate rule id(s); detections could not be "
               f"attributed to one rule")
    if missing_id:
        r.fail(f"{missing_id} rule(s) have no id")

    # ---- 3. generated searches parse --------------------------------
    scopes = be.load_scopes(Path(args.scopes))
    groups: Dict[tuple, List] = {}
    unscoped = []
    for x in rules:
        lvl = str(x.level).lower()
        if lvl not in be.TIERS:
            lvl = "medium"
        key, spl = be.resolve_scope(x, scopes)
        if not spl:
            unscoped.append(x)
        x._scope_key, x._scope_spl = key, spl
        groups.setdefault((x.platform, lvl, key), []).append(x)

    bad, batches_total, singles = [], 0, 0
    for (platform, lvl, skey), members in groups.items():
        # Rules that cannot be a search clause are deployed on their own, so
        # they do not take part in a batch and are not checked as one.
        def _batchable(x):
            c = be.rule_condition(x.splunk_search)
            return (be.search_clause_check(c)[0]
                    and not be.has_trailing_stages(x.splunk_search)
                    and be.selective(c))
        batchable = [x for x in members if _batchable(x)]
        singles += len(members) - len(batchable)
        if not batchable:
            continue
        for i, batch in enumerate(be.chunk_by_size(batchable, args.budget), 1):
            batches_total += 1
            # The clause grammar applies to the conditions this builder
            # assembles, not to the scope or the pipeline around them.
            prefilter = " OR ".join(
                f"({be.rule_condition(x.splunk_search)})" for x in batch)
            ok_b, why_b = be.search_clause_check(prefilter)
            if not ok_b:
                bad.append(f"{platform}/{lvl}/{skey} batch {i}: {why_b}")

    print(f"  [3] search syntax   {batches_total} batch(es) + {singles} standalone, "
          f"{len(bad)} malformed")
    if bad:
        for b in bad[:5]:
            print(f"                      {b}")
        r.fail(f"{len(bad)} batch(es) produce a search Splunk cannot parse; "
               f"each one disables every rule in it")

    # Individually, with the reason, so a rule is named rather than a batch.
    per_rule_bad = []
    for x in rules:
        cond = be.rule_condition(x.splunk_search)
        ok, why = be.search_clause_check(cond)
        if ok and be.has_trailing_stages(x.splunk_search):
            ok, why = False, "its matching continues past a pipeline stage"
        if ok and not be.selective(cond):
            ok, why = False, "the condition selects nothing — it would match every event"
        if not ok:
            if not cond and x.splunk_search.lstrip().startswith("|"):
                why = "starts with a pipeline stage"
            per_rule_bad.append((x, why))
    if per_rule_bad:
        print(f"                      {len(per_rule_bad)} rule(s) cannot be a search clause:")
        for x, why in per_rule_bad[:6]:
            print(f"                      {x.title[:48]:50} {why}")
        # Not a failure: build-engine deploys these on their own, where
        # Splunk parses the whole pipeline itself.
        r.warn(f"{len(per_rule_bad)} rule(s) are deployed individually rather "
               f"than batched")

    # ---- 4. log source mapping --------------------------------------
    print(f"  [4] log source      {len(groups)} group(s), "
          f"{len(unscoped)} rule(s) unmapped")
    if unscoped:
        kinds = collections.Counter(f"{x.product}/{x.category}" for x in unscoped)
        for k, n in kinds.most_common(5):
            print(f"                      {n:5}  {k}")
        r.warn(f"{len(unscoped)} rule(s) have no log source mapping and will "
               f"scan the whole index")

    # ---- 5. fields the rules need vs fields that exist ---------------
    needed = collections.Counter()
    per_rule_fields = {}
    for x in rules:
        f = referenced_fields(be.rule_condition(x.splunk_search))
        per_rule_fields[x.rule_id] = f
        needed.update(f)

    if args.fields and Path(args.fields).exists():
        have = {ln.strip() for ln in Path(args.fields).read_text().splitlines()
                if ln.strip() and not ln.startswith("#")}
        absent = {f: n for f, n in needed.items() if f not in have}
        dead = [x for x in rules
                if per_rule_fields.get(x.rule_id) and
                not (per_rule_fields[x.rule_id] & have)]
        print(f"  [5] field coverage  {len(needed) - len(absent)}/{len(needed)} "
              f"referenced fields exist; {len(dead)} rule(s) can never match")
        for f, n in sorted(absent.items(), key=lambda kv: -kv[1])[:8]:
            print(f"                      {n:5}  {f}")
        if dead:
            # Not a failure: a rule for telemetry this environment does not
            # collect is a coverage gap, not a defect.
            r.warn(f"{len(dead)} rule(s) reference no field this environment "
                   f"produces and cannot ever fire")
    else:
        print(f"  [5] field coverage  SKIPPED -- no --fields inventory given")
        print(f"                      {len(needed)} distinct fields referenced; "
              f"top: {', '.join(f for f, _ in needed.most_common(6))}")
        r.skip("field coverage: supply --fields to check that rules reference "
               "fields this environment actually produces")

    # ---- 6. can the instance carry the schedule ----------------------
    enabled = []
    for (platform, lvl, skey), members in groups.items():
        if not be.TIERS[lvl]["enabled"]:
            continue
        n = len(be.chunk_by_size(members, args.budget))
        interval = be.TIERS[lvl]["cron"]
        m = re.match(r"\*/(\d+)", interval)
        minutes = int(m.group(1)) if m else (60 if interval.startswith("0 ") else 1440)
        enabled.append((f"{platform}/{lvl}", n, minutes))

    worst = 0.0
    print(f"  [6] schedule        {sum(n for _, n, _ in enabled)} search(es) "
          f"enabled, {args.slots} slot(s) available")
    for label, n, minutes in sorted(enabled):
        # Searches of this tier that must complete inside one interval.
        load = (n * args.seconds_per_search) / (args.slots * minutes * 60)
        worst = max(worst, load)
        flag = "" if load < 0.5 else ("  TIGHT" if load < 1 else "  OVER CAPACITY")
        print(f"                      {label:28} {n:3} every {minutes:4}m  "
              f"{load*100:5.1f}% of capacity{flag}")
    if worst >= 1:
        r.fail("the schedule asks for more than the instance can run; the "
               "scheduler will defer searches and report nothing")
    elif worst >= 0.5:
        r.warn("the schedule uses more than half the available capacity, "
               "leaving little room for ad-hoc searching")

    # ---- verdict -----------------------------------------------------
    print()
    for s in r.skipped:
        print(f"  SKIPPED  {s}")
    for w in r.warnings:
        print(f"  WARNING  {w}")
    for f in r.failures:
        print(f"  FAILED   {f}")

    if r.failures or (args.strict and r.warnings):
        print(f"\n  NOT READY TO DEPLOY\n")
        return 1
    print(f"\n  ready: {converted} rules in {batches_total} batches\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
