#!/usr/bin/env python3
"""Build batched detection searches from a Sigma rule set.

One scheduled search per rule does not survive contact with a real instance.
Splunk caps concurrent scheduled searches at roughly half of
`max_searches_per_cpu * cpus + base_max_searches`; on a modest indexer that
is four. Several hundred rules against four slots means the scheduler defers
almost everything and detections never run at all.

This builds a small number of searches instead. Each one scans the index
once for the union of its rules' conditions, then names which rules matched
by testing each condition against only the events that got through. Rule
metadata lives in a lookup rather than on the stanza, so a dashboard reads
one small file instead of five hundred saved-search definitions.

Batches are grouped by platform and severity, because severity is what
decides how often a rule is worth running:

    critical   every 15 minutes
    high       every 30 minutes
    medium     hourly
    low        every 4 hours, shipped disabled
    info       every 6 hours, shipped disabled

The search window always equals the interval. Overlapping windows would
write the same detection twice; gaps are prevented by continuous scheduling
(`realtime_schedule = 0`) rather than by overlap.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "pylib"))

import yaml  # noqa: E402

import sigma2splunkalert as s2s  # noqa: E402

# Cadence, window and default state per severity. The window matches the
# interval so no detection is written twice.
TIERS: Dict[str, Dict] = {
    "critical":      {"cron": "*/15 * * * *", "window": "-15m", "enabled": True,
                      "priority": "higher"},
    "high":          {"cron": "*/30 * * * *", "window": "-30m", "enabled": True,
                      "priority": "higher"},
    "medium":        {"cron": "0 * * * *",    "window": "-60m", "enabled": True,
                      "priority": "default"},
    "low":           {"cron": "0 */4 * * *",  "window": "-4h",  "enabled": False,
                      "priority": "default"},
    "informational": {"cron": "0 */6 * * *",  "window": "-6h",  "enabled": False,
                      "priority": "default"},
}
TIER_ORDER = ["critical", "high", "medium", "low", "informational"]

LOOKUP_COLUMNS = [
    "sigma_rule_id", "sigma_rule", "sigma_level", "sigma_severity",
    "sigma_confidence", "sigma_confidence_score", "sigma_disposition",
    "sigma_min_matches", "sigma_platform", "sigma_log_source",
    "sigma_attack", "sigma_tactic", "sigma_technique", "sigma_technique_name",
    "sigma_tactic_name", "sigma_status", "sigma_author", "sigma_references",
    "sigma_falsepositives", "sigma_rule_date", "sigma_batch",
]


def rule_condition(splunk_search: str) -> str:
    """The rule's own matching expression.

    pySigma appends pipeline stages for some rules, and the converter adds
    its own. Only the leading expression can be tested with searchmatch, so
    anything from the first pipe onward is dropped and the rule is reported
    as partially batched.
    """
    return splunk_search.split(" | ", 1)[0].strip()


def has_trailing_stages(splunk_search: str) -> bool:
    return " | " in splunk_search


def spl_quote(condition: str) -> str:
    """Embed a search expression inside an SPL string literal."""
    return condition.replace("\\", "\\\\").replace('"', '\\"')


def load_scopes(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return doc.get("scopes", {}) or {}


def resolve_scope(rule, scopes: Dict[str, str]) -> tuple:
    """Where this rule's telemetry lives, most specific match first.

    Returns (key, spl). The key also groups the batches, so every rule in a
    batch shares one scope and the scope can be hoisted into the search.
    """
    product = (rule.product or "").lower()
    category = (rule.category or "").lower()
    service = (rule.service or "").lower()
    for key in (f"{product}/{category}/{service}" if service and category else None,
                f"{product}/{category}" if category else None,
                f"{product}/{service}" if service else None,
                product or None):
        if key and key in scopes:
            return key, scopes[key]
    return "unscoped", scopes.get("default", "")


def load_technique_names(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["technique_id"]: r for r in csv.DictReader(fh)}


def chunk_by_size(rules: List, budget: int) -> List[List]:
    """Group rules so no batch's conditions exceed the character budget.

    Each condition appears twice in the generated search, once in the scan
    filter and once in the attribution step, so the budget is half of what
    the finished search string will be.
    """
    batches: List[List] = []
    current: List = []
    size = 0
    for r in rules:
        c = len(rule_condition(r.splunk_search))
        # A rule larger than the whole budget gets a batch to itself rather
        # than being dropped.
        if current and size + c > budget:
            batches.append(current)
            current, size = [], 0
        current.append(r)
        size += c
    if current:
        batches.append(current)
    return batches


def build_search(batch: List, scope: str, alert_index: str,
                 logsource_scope: str = "") -> str:
    """One scan, then per-rule attribution over what survived the scan.

    The log source scope sits ahead of the rule conditions so the term index
    can reject whole buckets before any event is read. Every rule in the
    batch declared this log source, so the scope cannot exclude anything the
    batch could have matched.
    """
    conditions = [rule_condition(r.splunk_search) for r in batch]
    prefilter = " OR ".join(f"({c})" for c in conditions)
    scope = f"{scope} {logsource_scope}".strip() if logsource_scope else scope

    # searchmatch re-tests each condition against the events the scan
    # returned, which is what lets one search name which rule fired.
    tests = ", ".join(
        f'if(searchmatch("{spl_quote(c)}"),"{r.rule_id}",null())'
        for c, r in zip(conditions, batch)
    )

    return (
        f"{scope} ({prefilter})"
        f" | eval sigma_rule_id=mvappend({tests})"
        f" | where isnotnull(sigma_rule_id)"
        f" | mvexpand sigma_rule_id"
        # Aggregate per rule and host: a rule matching eighty events on one
        # host is one finding that says eighty, not eighty findings.
        f" | stats count as sigma_match_count, min(_time) as sigma_first_seen,"
        f" max(_time) as sigma_last_seen, earliest(_raw) as sigma_sample,"
        f" values(index) as sigma_src_index,"
        f" values(sourcetype) as sigma_src_sourcetype,"
        f" dc(host) as sigma_host_count"
        f" by sigma_rule_id, host"
        # Identity and severity come from the lookup, so adding a rule does
        # not mean rewriting a saved search.
        f" | lookup sigma_rules sigma_rule_id"
        f" | where sigma_match_count >= coalesce(sigma_min_matches, 1)"
        f" | eval _time=sigma_first_seen, sigma_src_host=host,"
        f" sigma_span_seconds=sigma_last_seen-sigma_first_seen"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+", help="Sigma rule folders or files")
    ap.add_argument("--config", "-c", default=str(HERE / "config.yaml"))
    ap.add_argument("--sigma-config", "-sc", default=str(HERE / "splunk-all.yml"))
    ap.add_argument("--pipeline", "-p", default="auto",
                    help="pySigma pipeline, or 'auto' to pick per rule from "
                         "its log source product")
    ap.add_argument("--out-conf", default=str(HERE / "app/sigma_detection_lab/default/savedsearches.conf"))
    ap.add_argument("--out-lookup", default=str(HERE / "app/sigma_detection_lab/lookups/sigma_rules.csv"))
    ap.add_argument("--mitre", default=str(HERE / "app/sigma_detection_lab/lookups/mitre_techniques.csv"))
    ap.add_argument("--scopes", default=str(HERE / "logsource-scope.yml"),
                    help="maps a Sigma log source to where it is indexed")
    ap.add_argument("--out-logic", default=str(HERE / "app/sigma_detection_lab/lookups/sigma_rule_logic.csv"),
                    help="per-rule detection logic, for the rule reference page")
    ap.add_argument("--budget", type=int, default=20000,
                    help="max characters of rule conditions per batch")
    ap.add_argument("--scope", default=None,
                    help="index scope prepended to every search")
    ap.add_argument("--window", default=None,
                    help="override every tier's search window, e.g. -7d. For "
                         "backfilling detections over data that is already "
                         "indexed. A window wider than the interval re-reads "
                         "the same events every run and writes the same "
                         "detection again, so this is not a production setting")
    ap.add_argument("--cron", default=None,
                    help="override every tier's cron, e.g. '0 3 * * *'")
    args = ap.parse_args(argv)

    config = s2s.openSigma2SplunkConfiguration(args.config)
    sigma_config = s2s.openSigmaConfiguration(args.sigma_config)
    # The per-rule emitter appends its own stages: a mitre_tags eval and a
    # collect. Both are replaced here by the rules lookup and the summary
    # index action, and anything after the condition cannot be tested with
    # searchmatch, so they are turned off for this build.
    config = dict(config)
    config["search_transformations"] = []
    config["summary_index"] = {"enabled": False}
    scope = args.scope or config.get("index_scope") or "`sigma_lab_index`"
    alert_index = ((config.get("alert_index") or {}).get("index")) or "sigma_alerts"
    techniques = load_technique_names(Path(args.mitre))

    files: List[str] = []
    for src in args.sources:
        files.extend(s2s.loadSigmaRules(src))
    print(f"  {len(files)} rule file(s)")

    rules, failed = [], 0
    reasons: Dict[str, int] = {}
    for f in files:
        pipeline = args.pipeline
        if pipeline == "auto":
            # The Windows pipeline renames Sysmon fields and adds the event
            # log scoping those rules assume. Applying it to a Linux rule
            # would rewrite fields that do not exist there.
            try:
                doc = yaml.safe_load(Path(f).read_text(encoding="utf-8")) or {}
                product = ((doc.get("logsource") or {}).get("product") or "").lower()
            except Exception:
                product = ""
            pipeline = "windows" if product == "windows" else "none"
        uc, err = s2s.process_rule(f, pipeline, config, sigma_config, "default")
        if uc is None:
            failed += 1
            key = err.split(":")[0][:60]
            reasons[key] = reasons.get(key, 0) + 1
            continue
        rules.append(uc)
    print(f"  {len(rules)} converted, {failed} could not be converted")
    for k, n in sorted(reasons.items(), key=lambda kv: -kv[1])[:5]:
        print(f"      {n:4}  {k}")

    # Group by platform, severity and log source. Severity decides the
    # cadence; the log source decides what the search is allowed to skip,
    # and a batch can only hoist a scope its rules all share.
    scopes = load_scopes(Path(args.scopes))
    groups: Dict[tuple, List] = {}
    scope_spl: Dict[str, str] = {}
    unscoped = 0
    for r in rules:
        lvl = str(r.level).lower()
        if lvl not in TIERS:
            lvl = "medium"
        key, spl = resolve_scope(r, scopes)
        if not spl:
            unscoped += 1
        scope_spl[key] = spl
        r._scope_key, r._scope_spl = key, spl
        groups.setdefault((r.platform, lvl, key), []).append(r)
    print(f"  {len(groups)} group(s) by platform / severity / log source")
    if unscoped:
        print(f"  {unscoped} rule(s) have no log source mapping and will scan "
              f"the whole index -- add them to {Path(args.scopes).name}")

    conf_parts: List[str] = []
    lookup_rows: List[Dict] = []
    total_batches = 0
    partial = 0

    conf_parts.append(
        "# Generated by bin/build-engine.py -- do not edit.\n"
        "#\n"
        "# Each stanza scans the index once for its rules' conditions and then\n"
        "# names which rules matched. Rule identity, severity and ATT&CK mapping\n"
        "# live in lookups/sigma_rules.csv, keyed on sigma_rule_id.\n"
    )

    for platform, lvl, skey in sorted(groups, key=lambda k: (k[0], TIER_ORDER.index(k[1]), k[2])):
            batch_rules = groups[(platform, lvl, skey)]
            ls_label = skey.split("/", 1)[1] if "/" in skey else skey
            tier = dict(TIERS[lvl])
            if args.window:
                tier["window"] = args.window
            if args.cron:
                tier["cron"] = args.cron
            batches = chunk_by_size(batch_rules, args.budget)
            for i, batch in enumerate(batches, 1):
                total_batches += 1
                name = (f"Sigma Engine - {platform} {ls_label} {lvl} "
                        f"{i:02d} of {len(batches):02d}")
                search = build_search(batch, scope, alert_index,
                                      scope_spl.get(skey, ""))

                conf_parts.append(f"""
# {len(batch)} rule(s), {platform} / {ls_label} / {lvl}.
# Scope: {scope_spl.get(skey, '(none -- scans the whole index)')}
[{name}]
search = {search}
description = {len(batch)} {lvl} {platform} Sigma rules, evaluated in one pass.
counttype = number of events
relation = greater than
quantity = 0
enableSched = 1
disabled = {0 if tier["enabled"] else 1}
realtime_schedule = 0
cron_schedule = {tier["cron"]}
dispatch.earliest_time = {tier["window"]}
dispatch.latest_time = now
allow_skew = 100%
schedule_priority = {tier["priority"]}
alert.digest_mode = 1
alert.track = 0
action.summary_index = 1
action.summary_index._name = {alert_index}
action.summary_index.sigma_batch = {name}
request.ui_dispatch_app = {config.get('app', 'sigma_detection_lab')}
request.ui_dispatch_view = search
""")

                for r in batch:
                    if has_trailing_stages(r.splunk_search):
                        partial += 1
                    techs = [t.replace("attack.", "").upper()
                             for t in r.mitre_techniques]
                    primary = techs[0] if techs else ""
                    meta = techniques.get(primary, {})
                    tactics = [t.replace("attack.", "") for t in r.mitre_tactics]
                    lookup_rows.append({
                        "sigma_rule_id": r.rule_id,
                        "sigma_rule": r.title,
                        "sigma_level": r.level,
                        "sigma_severity": r.severity,
                        "sigma_confidence": r.confidence,
                        "sigma_confidence_score": r.confidence_score,
                        "sigma_disposition": r.disposition,
                        "sigma_min_matches": 1 if r.disposition == "immediate" else 2,
                        "sigma_platform": r.platform,
                        "sigma_log_source": r.log_source,
                        "sigma_attack": ",".join(techs),
                        "sigma_tactic": ",".join(tactics),
                        "sigma_technique": primary,
                        # The readable name is resolved here so no dashboard
                        # has to join against ATT&CK to show a rule.
                        "sigma_technique_name": meta.get("display_name", "") or
                                                ("unmapped" if not primary else primary),
                        "sigma_tactic_name": meta.get("tactic_names", "") or
                                             ", ".join(t.replace("_", " ").title()
                                                       for t in tactics) or "unmapped",
                        "sigma_status": r.status,
                        "sigma_author": r.author,
                        "sigma_references": r.references,
                        "sigma_falsepositives": r.falsepositives,
                        "sigma_rule_date": r.modified or r.rule_date,
                        "sigma_batch": name,
                    })

    Path(args.out_conf).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_conf).write_text("".join(conf_parts), encoding="utf-8")

    Path(args.out_lookup).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_lookup, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LOOKUP_COLUMNS)
        w.writeheader()
        w.writerows(lookup_rows)

    # The detection logic itself, for the rule reference page. An operator
    # asked to act on a detection needs to see what the rule looks for and
    # why it was trusted, not just that it fired.
    logic_cols = ["sigma_rule_id", "sigma_rule", "sigma_description",
                  "sigma_detection_yaml", "sigma_condition", "sigma_spl",
                  "sigma_scope", "sigma_scope_key", "sigma_confidence_why",
                  "sigma_fields", "sigma_tags"]
    with open(args.out_logic, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=logic_cols)
        w.writeheader()
        for r in rules:
            det = (r.sigma_rule or {}).get("detection", {}) or {}
            w.writerow({
                "sigma_rule_id": r.rule_id,
                "sigma_rule": r.title,
                "sigma_description": r.description,
                # The author's own detection block, kept verbatim so the
                # page shows the rule rather than a paraphrase of it.
                "sigma_detection_yaml": yaml.safe_dump(
                    det, default_flow_style=False, sort_keys=False, width=100),
                "sigma_condition": str(det.get("condition", "")),
                "sigma_spl": rule_condition(r.splunk_search),
                "sigma_scope": getattr(r, "_scope_spl", ""),
                "sigma_scope_key": getattr(r, "_scope_key", ""),
                "sigma_confidence_why": " | ".join(r.confidence_why),
                "sigma_fields": ", ".join(r.fields),
                "sigma_tags": ", ".join(r.tags),
            })

    enabled = sum(1 for p in conf_parts if "\ndisabled = 0\n" in p)
    print(f"\n  {total_batches} batched search(es), {enabled} enabled by default")
    print(f"  {len(lookup_rows)} rules in the lookup")
    if partial:
        print(f"  {partial} rule(s) have stages after the condition; only the "
              f"condition is batched")
    longest = max((len(p) for p in conf_parts), default=0)
    print(f"  longest stanza: {longest} characters")
    print(f"\n  {args.out_conf}")
    print(f"  {args.out_lookup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
