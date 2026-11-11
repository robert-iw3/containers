#!/usr/bin/env python3

"""Check that seeded events really satisfy the rules they were planted for.

Runs entirely offline, before anything is indexed. Parses each generated
record back into fields the way a Splunk add-on would, then evaluates the
Sigma rule's detection against them.

This catches the failure that matters most in a detection lab: a planted
"positive" that does not actually satisfy its rule, which then reads as a
detection gap rather than a seeder bug. It also measures the benign
background for false positives.

Field extraction mirrors the add-ons, not Splunk itself, so a pass here
means the event is correct at the source. It does not prove Splunk's own
extractions agree; that needs the indexed data.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required")

# auditd hex-encodes any value containing whitespace or a quote.
HEX_RE = re.compile(r"^[0-9A-F]+$")


def dehex(value: str) -> str:
    if HEX_RE.match(value) and len(value) % 2 == 0 and len(value) > 2:
        try:
            return bytes.fromhex(value).decode("utf-8", "replace")
        except ValueError:
            return value
    return value


def parse_auditd(line: str) -> dict:
    """Extract key=value pairs from one auditd record, de-hexing as auditd does."""
    fields = {}
    for m in re.finditer(r'(\w+)=("([^"]*)"|[^\s]+)', line):
        key, raw, quoted = m.group(1), m.group(2), m.group(3)
        val = quoted if quoted is not None else raw
        fields[key] = dehex(val) if quoted is None else val
    # SYSCALL= / AUID= style trailing interpretations
    for m in re.finditer(r'\b([A-Z_]+)="([^"]*)"', line):
        fields.setdefault(m.group(1), m.group(2))
    return fields


def parse_winevent(line: str) -> dict:
    """Extract EventID plus the EventData Data elements, as the Windows and
    Sysmon add-ons present them."""
    fields = {}
    m = re.search(r"<EventID[^>]*>(\d+)</EventID>", line)
    if m:
        fields["EventID"] = m.group(1)
        fields["EventCode"] = m.group(1)
    m = re.search(r"<Computer>([^<]*)</Computer>", line)
    if m:
        fields["Computer"] = m.group(1)
    for k, v in re.findall(r'<Data Name="([^"]+)">([^<]*)</Data>', line):
        fields[k] = v
    return fields


def parse_secure(line: str) -> dict:
    fields = {"_raw": line}
    m = re.match(r"^(\S+)\s+(\S+)\s+(\w+)\[(\d+)\]:\s*(.*)$", line)
    if m:
        fields.update({"host": m.group(2), "process": m.group(3),
                       "pid": m.group(4), "message": m.group(5)})
    return fields


PARSERS = {
    "linux_audit": parse_auditd,
    "linux_secure": parse_secure,
    "bash_history": lambda l: {"_raw": l},
    "sysmon:linux": parse_winevent,
    "XmlWinEventLog:Security": parse_winevent,
    "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational": parse_winevent,
}


def match_value(actual, expected, modifier) -> bool:
    if actual is None:
        return False
    a, e = str(actual), str(expected)
    if modifier == "endswith":
        return a.lower().endswith(e.lower())
    if modifier == "startswith":
        return a.lower().startswith(e.lower())
    if modifier == "contains":
        return e.lower() in a.lower()
    if "*" in e:
        pat = "^" + re.escape(e).replace(r"\*", ".*") + "$"
        return re.match(pat, a, re.IGNORECASE) is not None
    return a.lower() == e.lower()


def match_selection(sel, fields) -> bool:
    """Evaluate one Sigma selection map against extracted fields. A list of
    values is an OR; separate keys are an AND."""
    if not isinstance(sel, dict):
        return False
    for key, expected in sel.items():
        field, _, modifier = key.partition("|")
        if modifier not in ("", "endswith", "startswith", "contains", "all"):
            return False
        values = expected if isinstance(expected, list) else [expected]
        # "all" means every value must match the same field.
        if modifier == "all":
            if not all(match_value(fields.get(field), v, "contains") for v in values):
                return False
            continue
        if not any(match_value(fields.get(field), v, modifier) for v in values):
            return False
    return True


def rule_matches(rule, fields) -> bool:
    det = rule.get("detection", {}) or {}
    condition = str(det.get("condition", "")).strip()
    sels = [k for k in det if k != "condition"]
    if len(sels) == 1 and condition in sels:
        return match_selection(det[sels[0]], fields)
    # Only single-selection rules are planted, so anything else is out of scope.
    return False


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeded", required=True, help="Directory from seed-events.py")
    ap.add_argument("--rules", required=True, help="Sigma rules directory")
    ap.add_argument("--show", type=int, default=8, help="How many failures to list")
    args = ap.parse_args(argv[1:])

    seeded = Path(args.seeded)
    truth = json.loads((seeded / "ground-truth.json").read_text(encoding="utf-8"))
    rules_dir = Path(args.rules)

    # Load only the rules that were planted.
    by_title = {}
    for title, meta in truth["rule_detail"].items():
        path = rules_dir / meta["file"]
        if not path.exists():
            continue
        by_title[title] = (yaml.safe_load(path.read_text(encoding="utf-8")), meta)

    # Index every seeded record by source type.
    records = defaultdict(list)
    for st, fname in truth["sourcetype_files"].items():
        path = Path(fname)
        if not path.exists():
            path = seeded / Path(fname).name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records[st].append(line)

    print(f"{'source type':<52} {'records':>9}")
    for st in sorted(records):
        print(f"{st:<52} {len(records[st]):>9,}")
    print()

    satisfied, unsatisfied = {}, {}
    fp_counter = Counter()

    for title, (rule, meta) in sorted(by_title.items()):
        st = meta["sourcetype"]
        parser = PARSERS.get(st)
        if parser is None:
            continue
        hits = 0
        for line in records.get(st, []):
            if rule_matches(rule, parser(line)):
                hits += 1
        expected = truth["expected_detections"][title]
        if hits >= expected:
            satisfied[title] = (hits, expected)
            if hits > expected:
                fp_counter[title] = hits - expected
        else:
            unsatisfied[title] = (hits, expected)

    total = len(by_title)
    print(f"planted rules checked:              {total}")
    print(f"rules whose planted events match:   {len(satisfied)}")
    print(f"rules whose planted events DO NOT:  {len(unsatisfied)}")
    print(f"rules matching MORE than planted:   {len(fp_counter)} "
          f"(benign background also matches)")

    if unsatisfied:
        print("\nSEEDER DEFECTS - planted event does not satisfy its own rule:")
        for title, (hits, exp) in list(unsatisfied.items())[:args.show]:
            meta = by_title[title][1]
            print(f"  {title}")
            print(f"      matched {hits}/{exp}  sourcetype={meta['sourcetype']}  "
                  f"file={meta['file']}")
            print(f"      planted fields: {meta['satisfied_fields']}")
        if len(unsatisfied) > args.show:
            print(f"  ... {len(unsatisfied)-args.show} more")

    if fp_counter:
        print("\nBackground also matches these rules (expected for broad rules):")
        for title, extra in fp_counter.most_common(args.show):
            print(f"  +{extra:<6} {title}")

    print()
    if unsatisfied:
        print("VERDICT: seeder has defects listed above. Fix before indexing, "
              "or those rules will read as detection gaps.")
        return 1
    print("VERDICT: every planted event satisfies its rule as written.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
