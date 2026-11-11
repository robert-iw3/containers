#!/usr/bin/env python3

"""Score Sigma rules against a labelled dataset, offline.

Converting a rule proves it compiles. Running it against data with known
answers is the only thing that shows whether its logic does what its author
meant. This evaluates each rule's full detection condition against every
event in a datagen scenario dataset, then scores it against the ground
truth:

  recall      of the true_positive instances, how many did a rule cover,
              broken out by adversary tier, because catching tier 1 and
              catching tier 4 are not the same claim
  precision   how often a rule fired on the false_positive bait or on
              ordinary baseline activity, which is what makes a rule
              unusable in production even when its recall is perfect
  silent      rules that never fired at all, split into "the data has no
              source it could match" and "the source is there and the rule
              still did not fire", because only the second is a rule problem

This is not Splunk. Field extraction here mirrors what the add-ons produce
and the condition evaluator implements Sigma's own semantics, so a result is
evidence about the rule's logic, not proof about a particular search head.
A rule that fails here will fail there; a rule that passes here still has to
be run against indexed data.

Standard library plus PyYAML.

  score-dataset.py --dataset ./out --rules ./rules/linux
  score-dataset.py --dataset ./out --rules ./rules --show-fp 20
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: python3 -m pip install --target ./pylib -r requirements.txt")


# ----------------------------------------------------------- field parsing

HEX_RE = re.compile(r"^[0-9A-F]+$")


def dehex(value):
    if HEX_RE.match(value) and len(value) % 2 == 0 and len(value) > 2:
        try:
            return bytes.fromhex(value).decode("utf-8", "replace")
        except ValueError:
            return value
    return value


def parse_auditd(line):
    """auditd records are key=value, and a value containing whitespace is
    hex-encoded, which is why a plain string search for a command line with
    spaces fails against real data."""
    fields = {}
    for m in re.finditer(r'(\w+)=("([^"]*)"|[^\s]+)', line):
        key, raw, quoted = m.group(1), m.group(2), m.group(3)
        fields[key] = quoted if quoted is not None else dehex(raw)
    return fields


def parse_winevent(line):
    """EventID plus the EventData Data elements, as the Windows and Sysmon
    add-ons present them after index-time XML extraction."""
    fields = {}
    m = re.search(r"<EventID[^>]*>(\d+)</EventID>", line)
    if m:
        fields["EventID"] = m.group(1)
        fields["EventCode"] = m.group(1)
    for tag, key in (("Computer", "Computer"), ("Channel", "Channel")):
        m = re.search(rf"<{tag}>([^<]*)</{tag}>", line)
        if m:
            fields[key] = m.group(1)
    for k, v in re.findall(r'<Data Name="([^"]+)">([^<]*)</Data>', line):
        fields[k] = v
    # Sysmon's own field names are what most rules use; the Security channel
    # calls the same things something else, so both are offered.
    if "NewProcessName" in fields:
        fields.setdefault("Image", fields["NewProcessName"])
    if "ParentProcessName" in fields:
        fields.setdefault("ParentImage", fields["ParentProcessName"])
    return fields


def parse_syslog(line):
    fields = {"_raw": line}
    m = re.match(r"^(\S+\s+\S+\s+\S+|\S+)\s+(\S+)\s+([\w./-]+)(?:\[(\d+)\])?:\s*(.*)$", line)
    if m:
        fields.update({"host": m.group(2), "process": m.group(3),
                       "pid": m.group(4) or "", "message": m.group(5)})
    for k, v in re.findall(r'(\w+)=("[^"]*"|\S+)', line):
        fields.setdefault(k, v.strip('"'))
    return fields


PARSERS = {
    "linux_audit": parse_auditd,
    "linux_secure": parse_syslog,
    "syslog": parse_syslog,
    "bash_history": lambda l: {"_raw": l},
    "sysmon:linux": parse_winevent,
    "XmlWinEventLog:Security": parse_winevent,
    "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational": parse_winevent,
}

# Which source type a rule's log source is satisfied by in this dataset.
LOGSOURCE_MAP = [
    (("linux", "process_creation", None), "sysmon:linux"),
    (("linux", "file_event", None), "sysmon:linux"),
    (("linux", "network_connection", None), "sysmon:linux"),
    (("linux", None, "auditd"), "linux_audit"),
    (("linux", None, "syslog"), "syslog"),
    (("linux", None, "sshd"), "linux_secure"),
    (("linux", None, "cron"), "syslog"),
    (("linux", None, None), "linux_secure"),
    (("windows", "process_creation", None),
     "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational"),
    (("windows", None, "sysmon"),
     "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational"),
    (("windows", None, None), "XmlWinEventLog:Security"),
]


def sourcetypes_for(rule):
    ls = rule.get("logsource") or {}
    p, c, s = ls.get("product"), ls.get("category"), ls.get("service")
    out = []
    for (mp, mc, ms), st in LOGSOURCE_MAP:
        if mp and mp != p:
            continue
        if mc and mc != c:
            continue
        if ms and ms != s:
            continue
        if mc is None and ms is None and (c or s) and out:
            continue
        out.append(st)
    return out[:1] if out else []


# -------------------------------------------------------- value matching

def match_value(actual, expected, modifiers):
    if actual is None:
        return False
    a = str(actual)
    e = str(expected)
    if "re" in modifiers:
        try:
            return re.search(e, a, re.IGNORECASE) is not None
        except re.error:
            return False
    if "base64offset" in modifiers or "base64" in modifiers:
        # Not evaluated: the encoded form depends on offset and alphabet, so
        # a result either way would be misleading.
        return False
    if "cidr" in modifiers:
        try:
            import ipaddress
            return ipaddress.ip_address(a) in ipaddress.ip_network(e, strict=False)
        except Exception:
            return False
    al, el = a.lower(), e.lower()
    if "endswith" in modifiers:
        return al.endswith(el)
    if "startswith" in modifiers:
        return al.startswith(el)
    if "contains" in modifiers:
        return el in al
    if "gt" in modifiers or "gte" in modifiers or "lt" in modifiers or "lte" in modifiers:
        try:
            an, en = float(a), float(e)
        except ValueError:
            return False
        if "gt" in modifiers:  return an > en
        if "gte" in modifiers: return an >= en
        if "lt" in modifiers:  return an < en
        return an <= en
    if "*" in e or "?" in e:
        pat = "^" + re.escape(e).replace(r"\*", ".*").replace(r"\?", ".") + "$"
        return re.match(pat, a, re.IGNORECASE) is not None
    return al == el


def match_selection(sel, fields):
    """One Sigma selection. A map is AND across keys, a list of values is OR
    within a key, and a list of maps is OR across the maps."""
    if isinstance(sel, list):
        if all(isinstance(x, dict) for x in sel) and sel:
            return any(match_selection(x, fields) for x in sel)
        # A bare list is a keyword search over the whole event.
        raw = fields.get("_raw") or " ".join(str(v) for v in fields.values())
        return any(str(k).lower() in raw.lower() for k in sel)
    if not isinstance(sel, dict):
        return False
    for key, expected in sel.items():
        parts = key.split("|")
        field, modifiers = parts[0], set(parts[1:])
        values = expected if isinstance(expected, list) else [expected]
        if "all" in modifiers:
            mods = modifiers - {"all"} or {"contains"}
            if not all(match_value(fields.get(field), v, mods) for v in values):
                return False
            continue
        if "exists" in modifiers:
            want = bool(values[0]) if values else True
            if (fields.get(field) is not None) != want:
                return False
            continue
        if not any(match_value(fields.get(field), v, modifiers) for v in values):
            return False
    return True


# ------------------------------------------------------ condition parsing

TOKEN = re.compile(r"\(|\)|\b(?:and|or|not)\b|\b(?:1|all)\s+of\s+[\w*]+|[\w*]+",
                   re.IGNORECASE)


def evaluate_condition(condition, detection, fields):
    """Evaluate a Sigma condition expression.

    Supports and / or / not, parentheses, and the "1 of" and "all of"
    quantifiers over a wildcard group or "them". Anything outside that is
    reported to the caller as unsupported rather than guessed at, because a
    wrong answer here looks like a rule defect.
    """
    tokens = TOKEN.findall(condition)
    tokens = [t for t in (x.strip() for x in tokens) if t]
    pos = 0

    def sel_value(name):
        if name in detection:
            return match_selection(detection[name], fields)
        raise KeyError(name)

    def quantifier(tok):
        m = re.match(r"(1|all)\s+of\s+([\w*]+)", tok, re.IGNORECASE)
        qty, group = m.group(1).lower(), m.group(2)
        if group.lower() == "them":
            names = [k for k in detection if k != "condition"]
        elif "*" in group:
            rx = re.compile("^" + re.escape(group).replace(r"\*", ".*") + "$")
            names = [k for k in detection if k != "condition" and rx.match(k)]
        else:
            names = [group]
        if not names:
            raise KeyError(group)
        results = [match_selection(detection[n], fields) for n in names
                   if n in detection]
        return all(results) if qty == "all" else any(results)

    def parse_or():
        nonlocal pos
        val = parse_and()
        while pos < len(tokens) and tokens[pos].lower() == "or":
            pos += 1
            val = parse_and() or val
        return val

    def parse_and():
        nonlocal pos
        val = parse_not()
        while pos < len(tokens) and tokens[pos].lower() == "and":
            pos += 1
            val = parse_not() and val
        return val

    def parse_not():
        nonlocal pos
        if pos < len(tokens) and tokens[pos].lower() == "not":
            pos += 1
            return not parse_not()
        return parse_atom()

    def parse_atom():
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError("truncated condition")
        tok = tokens[pos]
        if tok == "(":
            pos += 1
            val = parse_or()
            if pos < len(tokens) and tokens[pos] == ")":
                pos += 1
            return val
        pos += 1
        if re.match(r"(1|all)\s+of\s+", tok, re.IGNORECASE):
            return quantifier(tok)
        return sel_value(tok)

    result = parse_or()
    if pos != len(tokens):
        raise ValueError(f"unparsed tail: {' '.join(tokens[pos:])}")
    return result


# ------------------------------------------------------------------ main

def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True,
                    help="Directory from scenario.py, holding ground-truth.json")
    ap.add_argument("--rules", required=True, help="Sigma rules directory")
    ap.add_argument("--show-fp", type=int, default=12,
                    help="How many false-positive-prone rules to list")
    ap.add_argument("--show-hits", type=int, default=12)
    ap.add_argument("--out", default=None, help="Write the full result as JSON")
    args = ap.parse_args(argv[1:])

    ds = Path(args.dataset)
    truth = json.loads((ds / "ground-truth.json").read_text(encoding="utf-8"))

    # Index every event by source type, keeping its line number so a hit can
    # be attributed to a scenario instance by time window later.
    events = defaultdict(list)
    for st, fname in truth["files"].items():
        path = ds / fname
        if not path.exists():
            continue
        parser = PARSERS.get(st)
        if parser is None:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events[st].append((line, parser(line)))
    total_events = sum(len(v) for v in events.values())
    if not total_events:
        sys.exit(f"no parsable events in {ds}")

    # Attribution is by the digest of the event line, which scenario.py
    # recorded when it planted it. Matching on identifier values instead
    # credits hits to the wrong instance: the values span several steps, so
    # no single event carries all of them.
    instances = truth["instances"]
    digest_owner = {}
    for i, inst in enumerate(instances):
        for d in inst.get("event_sha1") or []:
            digest_owner.setdefault(d, []).append(i)
    if not digest_owner:
        print("\nWARNING: this dataset has no event digests, so planted events "
              "cannot be attributed.\n         Regenerate it with a current "
              "scenario.py.", file=sys.stderr)

    def attribute(line):
        return digest_owner.get(hashlib.sha1(line.encode()).hexdigest()[:16], [])

    rules = []
    for f in sorted(Path(args.rules).rglob("*.yml")):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and d.get("detection") and d.get("title"):
            d["_file"] = str(f.relative_to(Path(args.rules)))
            rules.append(d)

    print(f"dataset:  {total_events:,} events across {len(events)} source type(s)")
    print(f"          {len(instances)} planted instance(s)")
    print(f"rules:    {len(rules)}")

    verdicts = Counter()
    per_rule = {}
    unsupported = Counter()

    for rule in rules:
        det = rule["detection"]
        cond = det.get("condition")
        sts = sourcetypes_for(rule)
        if not sts:
            verdicts["no_source_mapping"] += 1
            continue
        pool = [(l, f) for st in sts for (l, f) in events.get(st, [])]
        if not pool:
            verdicts["source_absent_from_dataset"] += 1
            continue
        if not isinstance(cond, str):
            verdicts["unsupported_condition"] += 1
            unsupported["condition is a list, not a string"] += 1
            continue

        tp_inst, fp_inst, baseline_hits, matched = set(), set(), 0, 0
        broke = None
        for line, fields in pool:
            try:
                hit = evaluate_condition(cond, det, fields)
            except KeyError as e:
                broke = f"references {e} which the detection does not define"
                break
            except Exception as e:
                broke = f"{type(e).__name__}: {e}"
                break
            if not hit:
                continue
            matched += 1
            owners = attribute(line)
            if owners:
                for oi in owners:
                    if instances[oi]["label"] == "true_positive":
                        tp_inst.add(oi)
                    else:
                        fp_inst.add(oi)
            else:
                baseline_hits += 1
        if broke:
            verdicts["unsupported_condition"] += 1
            unsupported[broke[:90]] += 1
            continue

        verdicts["evaluated"] += 1
        per_rule[rule["title"]] = {
            "file": rule["_file"],
            "level": rule.get("level", "medium"),
            "condition": cond,
            "sourcetypes": sts,
            "events_matched": matched,
            "tp_instances": sorted(tp_inst),
            "fp_instances": sorted(fp_inst),
            "baseline_events": baseline_hits,
        }

    print("\n=== rule evaluation ===")
    for k in ("evaluated", "source_absent_from_dataset", "no_source_mapping",
              "unsupported_condition"):
        if verdicts[k]:
            print(f"  {verdicts[k]:>5}  {k}")
    if unsupported:
        print("\n  conditions this evaluator does not implement:")
        for msg, n in unsupported.most_common(5):
            print(f"    {n:>4}x {msg}")

    # Recall per tier: a true_positive instance is covered if any rule hit it.
    covered = defaultdict(set)
    for title, r in per_rule.items():
        for i in r["tp_instances"]:
            covered[instances[i]["tier"]].add(i)
    by_tier = defaultdict(set)
    for i, inst in enumerate(instances):
        if inst["label"] == "true_positive":
            by_tier[inst["tier"]].add(i)

    print("\n=== recall by adversary tier ===")
    print(f"  {'tier':<24} {'instances':>9} {'detected':>9}  scenarios missed")
    for tier in sorted(by_tier):
        total_t = by_tier[tier]
        got = covered.get(tier, set())
        missed = sorted({instances[i]["scenario"] for i in (total_t - got)})
        name = instances[next(iter(total_t))]["tier_name"]
        print(f"  {tier} {name:<22} {len(total_t):>9} {len(got):>9}  "
              f"{', '.join(missed) or '-'}")

    fp_prone = sorted(
        ((t, r) for t, r in per_rule.items() if r["fp_instances"] or r["baseline_events"]),
        key=lambda x: -(len(x[1]["fp_instances"]) * 1000 + x[1]["baseline_events"]))
    print(f"\n=== rules that fired on benign activity: {len(fp_prone)} ===")
    if fp_prone:
        print("  These are what make a rule unusable in production. A rule")
        print("  firing on the bait scenarios is matching legitimate work.")
        print(f"\n  {'rule':<52} {'bait':>5} {'baseline':>9} {'level':<9}")
        for title, r in fp_prone[:args.show_fp]:
            print(f"  {title[:50]:<52} {len(r['fp_instances']):>5} "
                  f"{r['baseline_events']:>9} {r['level']:<9}")

    hits = sorted(((t, r) for t, r in per_rule.items() if r["tp_instances"]),
                  key=lambda x: -len(x[1]["tp_instances"]))
    print(f"\n=== rules that caught planted attacks: {len(hits)} ===")
    for title, r in hits[:args.show_hits]:
        tiers = sorted({instances[i]["tier"] for i in r["tp_instances"]})
        clean = "" if (r["fp_instances"] or r["baseline_events"]) else "  clean"
        print(f"  tier {','.join(map(str, tiers))}  {title[:60]}{clean}")

    silent = [t for t, r in per_rule.items()
              if not r["tp_instances"] and not r["fp_instances"]
              and not r["baseline_events"]]
    print(f"\n=== evaluated but never fired: {len(silent)} ===")
    print("  Their source type is present, so this is the rule's own logic")
    print("  or activity the dataset does not contain.")

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"dataset": str(ds), "totals": dict(verdicts),
             "rules": per_rule,
             "recall_by_tier": {str(k): {"instances": len(v),
                                         "detected": len(covered.get(k, set()))}
                                for k, v in by_tier.items()}}, indent=1),
            encoding="utf-8")
        print(f"\nfull result: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
