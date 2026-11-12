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
# Each tier runs on its own cadence and looks back over exactly that
# interval. The window must not be wider: a wider window re-reads events the
# previous run already matched and records the same detection again. Gaps
# are prevented by continuous scheduling instead -- see realtime_schedule
# below -- which anchors each run's time range to its scheduled time, so a
# run that starts late still covers the window it was meant to.
#
# "spread" is how many minutes the scheduler may defer a search to even out
# load. Every search in a tier is scheduled on the same minute and an
# instance runs only a handful at once, so without a spread they queue and
# each one's start time walks further from its schedule.
#
# schedule_window rather than allow_skew, for two reasons: Splunk counts a
# skewed search as delayed in its own health reporting but a deferral inside
# schedule_window as on time, and allow_skew applies only to */N crons, so
# it does nothing for the hourly tier.
TIERS: Dict[str, Dict] = {
    "critical":      {"cron": "*/15 * * * *", "window": "-15m", "spread": 5,
                      "enabled": True,  "priority": "higher"},
    "high":          {"cron": "*/30 * * * *", "window": "-30m", "spread": 10,
                      "enabled": True,  "priority": "higher"},
    "medium":        {"cron": "0 * * * *",    "window": "-60m", "spread": 20,
                      "enabled": True,  "priority": "default"},
    "low":           {"cron": "0 */4 * * *",  "window": "-4h",  "spread": 60,
                      "enabled": False, "priority": "default"},
    "informational": {"cron": "0 */6 * * *",  "window": "-6h",  "spread": 60,
                      "enabled": False, "priority": "default"},
}
TIER_ORDER = ["critical", "high", "medium", "low", "informational"]

# How many searches have been emitted on each tier so far, so each one gets
# its own minute rather than sharing with the rest of its tier.
_TIER_SEQ: Dict[str, int] = {}


def staggered_cron(cron: str, offset: int) -> str:
    """The same interval, started `offset` minutes later.

    Every search in a tier shares a cron, so they all fire on the same
    minute and queue behind the handful an instance runs at once. Each one
    then starts further from its schedule than the last, and every run is
    reported as delayed. schedule_window lets the scheduler move them, which
    spreads the load, but the run is still counted against its original
    schedule -- a search deferred five minutes is still five minutes late.
    Giving each its own offset is what actually stops the queue.
    """
    parts = cron.split()
    if len(parts) != 5:
        return cron
    minute, hour = parts[0], parts[1]
    if minute.startswith("*/"):
        try:
            step = int(minute[2:])
        except ValueError:
            return cron
        if step <= 0 or step > 59:
            return cron
        mins = sorted((offset % step) + k * step for k in range(60 // step))
        return ",".join(str(m) for m in mins) + " " + " ".join(parts[1:])
    if minute.isdigit():
        # Hourly or daily: move it within the hour.
        return " ".join([str(offset % 60)] + parts[1:])
    return cron


def tier_cron(tier_name: str, tier: Dict) -> str:
    """This tier's cron, offset so no two of its searches collide."""
    n = _TIER_SEQ.get(tier_name, 0)
    _TIER_SEQ[tier_name] = n + 1
    return staggered_cron(tier["cron"], n)



LOOKUP_COLUMNS = [
    "sigma_rule_id", "sigma_rule", "sigma_level", "sigma_severity",
    "sigma_confidence", "sigma_confidence_score", "sigma_disposition",
    "sigma_min_matches", "sigma_platform", "sigma_log_source",
    "sigma_attack", "sigma_tactic", "sigma_technique", "sigma_technique_name",
    "sigma_tactic_name", "sigma_status", "sigma_author", "sigma_references",
    "sigma_falsepositives", "sigma_rule_date", "sigma_batch",
    "sigma_source_path", "sigma_source_url",
]


def _split_stage(splunk_search: str) -> int:
    """Offset of the first pipeline separator that is not inside a string.

    Rules that hunt for shell pipelines carry a literal pipe in their match
    text -- "* | iex;*", "/bin/sh | nc". Splitting on the first " | " found
    anywhere cuts through the middle of that string literal, and the
    resulting fragment has unbalanced quotes and parentheses. Splunk then
    rejects the whole batched search, so one such rule silently disables
    every rule batched with it.
    """
    # A rule can convert to SPL that *starts* with a pipeline stage, when its
    # detection needs a rex before anything can be matched. There is no
    # leading space in front of that pipe, so looking only for " | " misses
    # it, and the whole rule is then treated as a search clause. Embedded in
    # a batch that produces "(| rex ...)", which is never valid and takes
    # every rule in the batch down with it.
    if splunk_search.lstrip().startswith("|"):
        return 0

    in_quote = False
    i = 0
    while i < len(splunk_search):
        c = splunk_search[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            in_quote = not in_quote
        elif not in_quote and splunk_search[i:i + 3] == " | ":
            return i
        i += 1
    return -1


def rule_condition(splunk_search: str) -> str:
    """The rule's own matching expression.

    pySigma appends pipeline stages for some rules, and the converter adds
    its own. Only the leading expression can be tested with searchmatch, so
    anything from the first real pipeline stage onward is dropped and the
    rule is reported as partially batched.
    """
    cut = _split_stage(splunk_search)
    return (splunk_search if cut == -1 else splunk_search[:cut]).strip()


def has_trailing_stages(splunk_search: str) -> bool:
    return _split_stage(splunk_search) != -1


def spl_quote(condition: str) -> str:
    """Embed a search expression inside an SPL string literal."""
    return condition.replace("\\", "\\\\").replace('"', '\\"')


def search_clause_check(expr: str):
    """Is this text safe to embed as a search clause, and inside searchmatch?

    This is deliberately an allowlist. An earlier version asked the opposite
    question -- "can I find something wrong with it" -- and passed two
    searches that Splunk then rejected at run time, each taking a whole
    batch of rules down with it. A checker that approximates another
    parser must fail closed: anything it cannot positively account for is
    rejected and the rule is deployed on its own, where Splunk parses the
    whole pipeline itself.

    Returns (ok, reason). reason is empty when ok.
    """
    if not expr or not expr.strip():
        return False, "empty condition"

    depth = 0
    i = 0
    n = len(expr)
    while i < n:
        c = expr[i]

        # A double-quoted string. Inside it, only \" and \\ are escapes;
        # everything else, parentheses included, is literal text.
        if c == '"':
            i += 1
            closed = False
            while i < n:
                if expr[i] == "\\":
                    if i + 1 >= n:
                        return False, "a backslash ends the condition inside a string"
                    i += 2
                    continue
                if expr[i] == '"':
                    closed = True
                    i += 1
                    break
                i += 1
            if not closed:
                return False, "an unterminated quoted string"
            continue

        # Anything that turns a clause into a pipeline, a macro expansion or
        # a subsearch cannot be embedded, and cannot be tested by
        # searchmatch either.
        if c == "|":
            return False, "contains a pipeline stage"
        if c == "`":
            return False, "contains a macro expansion"
        if c == "[":
            return False, "contains a subsearch"
        if c == "]":
            return False, "contains a stray subsearch bracket"

        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth < 0:
                return False, "a closing parenthesis with nothing open"
        elif c == "\\":
            # Outside a string a backslash is not meaningful to the parser,
            # and pySigma should not emit one. Reject rather than guess.
            return False, "a backslash outside a quoted string"
        i += 1

    if depth != 0:
        return False, f"{depth} unclosed parenthesis/es"
    return True, ""


def selective(condition: str) -> bool:
    """Does this condition actually narrow anything?

    A rule whose matching logic lives entirely in a trailing pipeline stage
    converts to a bare "*". Batched, its prefilter disjunct matches every
    event in scope and its searchmatch test is true for all of them, so the
    batch attributes every event to that rule. The detection index then
    fills with high severity findings for ordinary activity, which is worse
    than missing the rule.
    """
    stripped = condition.replace("*", "").replace("(", "").replace(")", "").strip()
    return bool(stripped)


def balanced(expr: str) -> bool:
    """Back-compatible wrapper. Prefer search_clause_check for the reason."""
    return search_clause_check(expr)[0]


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


def source_url(path: str, repo_branch: str) -> tuple:
    """The rule's path within SigmaHQ, and a link to the file.

    The fetched tree nests the rules under a package directory, so the part
    that matches the repository starts at the first "rules" segment.
    """
    parts = Path(path).parts
    for i, seg in enumerate(parts):
        if seg in ("rules", "rules-emerging-threats", "rules-threat-hunting",
                   "rules-compliance", "rules-dfir", "rules-placeholder"):
            rel = "/".join(parts[i:])
            return rel, f"https://github.com/SigmaHQ/sigma/blob/{repo_branch}/{rel}"
    return "", ""


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
    # returned, which is what lets one search name which rule fired. A miss
    # contributes an empty string rather than a null: mvappend returns null
    # as soon as any argument is null, and in a batch of fifty rules nearly
    # every test is a miss, so an mvappend of the results was null on every
    # event and the engine reported nothing at all. Concatenating has no
    # multivalue null semantics to get wrong.
    tests = " . ".join(
        f'if(searchmatch("{spl_quote(c)}"),"{r.rule_id},","")'
        for c, r in zip(conditions, batch)
    )

    return (
        f"{scope} ({prefilter})"
        f" | eval sigma_hits={tests}"
        f' | where sigma_hits!=""'
        f" | eval sigma_rule_id=split(substr(sigma_hits,1,len(sigma_hits)-1),\",\")"
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
        f" | eval _time=sigma_first_seen, sigma_src_host=host,"
        f" sigma_span_seconds=sigma_last_seen-sigma_first_seen,"
        f" sigma_corroborated=if(sigma_match_count >="
        f" coalesce(sigma_min_matches, 1), \"yes\", \"no\")"
    )


def build_single_search(rule, scope: str, logsource_scope: str) -> str:
    """One rule that has to keep its own pipeline.

    The scope supplies the events the rule's first stage needs, then the
    rule's own SPL runs unchanged, then the same aggregation every batch
    uses so the detection it writes is identical in shape.
    """
    full_scope = f"{scope} {logsource_scope}".strip() if logsource_scope else scope
    spl = rule.splunk_search.strip()
    joiner = " " if spl.startswith("|") else " "
    return (
        f"{full_scope}{joiner}{spl}"
        f' | eval sigma_rule_id="{rule.rule_id}"'
        f" | stats count as sigma_match_count, min(_time) as sigma_first_seen,"
        f" max(_time) as sigma_last_seen, earliest(_raw) as sigma_sample,"
        f" values(index) as sigma_src_index,"
        f" values(sourcetype) as sigma_src_sourcetype,"
        f" dc(host) as sigma_host_count"
        f" by sigma_rule_id, host"
        f" | lookup sigma_rules sigma_rule_id"
        f" | eval _time=sigma_first_seen, sigma_src_host=host,"
        f" sigma_span_seconds=sigma_last_seen-sigma_first_seen,"
        f" sigma_corroborated=if(sigma_match_count >="
        f" coalesce(sigma_min_matches, 1), \"yes\", \"no\")"
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
    ap.add_argument("--branch", default="master",
                    help="SigmaHQ branch the reference links point at")
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
    unbatchable: List = []
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
        uc._source_path = f
        cond = rule_condition(uc.splunk_search)
        ok, why = search_clause_check(cond)
        if ok and has_trailing_stages(uc.splunk_search):
            ok, why = False, "its matching continues past a pipeline stage"
        if ok and not selective(cond):
            ok, why = False, "the condition selects nothing — it would match every event"
        if not ok:
            if not cond and uc.splunk_search.lstrip().startswith("|"):
                why = "starts with a pipeline stage"
            unbatchable.append((uc, why))
            continue
        rules.append(uc)
    print(f"  {len(rules)} converted, {failed} could not be converted")
    if unbatchable:
        print(f"  {len(unbatchable)} rule(s) need a pipeline stage before they "
              f"can match; deployed individually:")
        for u, why in unbatchable[:8]:
            print(f"      {u.title[:52]:54} {why}")
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
    bad_batches: List[str] = []

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
                # A search that does not parse takes its whole batch down
                # with it, and says so only in scheduler.log. Catch it here.
                # Only the scan clause is checked against the clause grammar:
                # everything from the first eval onward is a pipeline, which
                # that grammar rejects by design.
                # The scope legitimately contains an index macro, so the
                # clause grammar is applied to the rule conditions only --
                # the part this builder assembles and is responsible for.
                prefilter = " OR ".join(
                    f"({rule_condition(x.splunk_search)})" for x in batch)
                ok_b, why_b = search_clause_check(prefilter)
                if not ok_b:
                    bad_batches.append(f"{name}: {why_b}")

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
cron_schedule = {tier_cron(lvl, tier)}
dispatch.earliest_time = {tier["window"]}
dispatch.latest_time = now
schedule_window = {tier['spread']}
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
                        "sigma_source_path": source_url(getattr(r, "_source_path", ""), args.branch)[0],
                        "sigma_source_url": source_url(getattr(r, "_source_path", ""), args.branch)[1],
                    })

    for uc, why in unbatchable:
        lvl = str(uc.level).lower()
        if lvl not in TIERS:
            lvl = "medium"
        tier = dict(TIERS[lvl])
        if args.window:
            tier["window"] = args.window
        if args.cron:
            tier["cron"] = args.cron
        key, ls_spl = resolve_scope(uc, scopes)
        name = f"Sigma Rule - {uc.title[:70]}"
        total_batches += 1
        conf_parts.append(f"""
# One rule, on its own: {why}.
[{name}]
search = {build_single_search(uc, scope, ls_spl)}
description = {uc.title} ({uc.level}). Runs alone because it {why}.
counttype = number of events
relation = greater than
quantity = 0
enableSched = 1
disabled = {0 if tier["enabled"] else 1}
realtime_schedule = 0
cron_schedule = {tier_cron(lvl, tier)}
dispatch.earliest_time = {tier["window"]}
dispatch.latest_time = now
schedule_window = {tier['spread']}
schedule_priority = {tier["priority"]}
alert.digest_mode = 1
alert.track = 0
action.summary_index = 1
action.summary_index._name = {alert_index}
action.summary_index.sigma_batch = {name}
request.ui_dispatch_app = {config.get('app', 'sigma_detection_lab')}
request.ui_dispatch_view = search
""")
        techs = [t.replace("attack.", "").upper() for t in uc.mitre_techniques]
        primary = techs[0] if techs else ""
        meta = techniques.get(primary, {})
        tactics = [t.replace("attack.", "") for t in uc.mitre_tactics]
        lookup_rows.append({
            "sigma_rule_id": uc.rule_id, "sigma_rule": uc.title,
            "sigma_level": uc.level, "sigma_severity": uc.severity,
            "sigma_confidence": uc.confidence,
            "sigma_confidence_score": uc.confidence_score,
            "sigma_disposition": uc.disposition,
            "sigma_min_matches": 1 if uc.disposition == "immediate" else 2,
            "sigma_platform": uc.platform, "sigma_log_source": uc.log_source,
            "sigma_attack": ",".join(techs), "sigma_tactic": ",".join(tactics),
            "sigma_technique": primary,
            "sigma_technique_name": meta.get("display_name", "") or ("unmapped" if not primary else primary),
            "sigma_tactic_name": meta.get("tactic_names", "") or "unmapped",
            "sigma_status": uc.status, "sigma_author": uc.author,
            "sigma_references": uc.references,
            "sigma_falsepositives": uc.falsepositives,
            "sigma_rule_date": uc.modified or uc.rule_date,
            "sigma_batch": name,
            "sigma_source_path": source_url(getattr(uc, "_source_path", ""), args.branch)[0],
            "sigma_source_url": source_url(getattr(uc, "_source_path", ""), args.branch)[1],
        })
        uc._scope_key, uc._scope_spl = key, ls_spl
        rules.append(uc)

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
    if bad_batches:
        print(f"\n  REFUSED: {len(bad_batches)} batch(es) do not parse:")
        for b in bad_batches[:5]:
            print(f"      {b}")
        raise SystemExit("a malformed batch disables every rule in it; "
                         "not writing the engine")
    longest = max((len(p) for p in conf_parts), default=0)
    print(f"  longest stanza: {longest} characters")
    print(f"\n  {args.out_conf}")
    print(f"  {args.out_lookup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
