#!/usr/bin/env python3
# ==============================================================================
# toggle_rule_blocking.py -- risk-based rule action controller for Suricata IPS
#
# Flips Suricata rule actions (alert <-> drop <-> reject) according to a policy,
# so the SAME ruleset can run detection-only or actively block, and so blocking
# can be scoped to a risk tier instead of "all or nothing".
#
# Risk model (maps to the rule files shipped in this image):
#   tier 1  block-known-bad.rules   high confidence     -> drop  (block known bad)
#   tier 2  suspicious.rules        medium              -> alert (rate_filter escalates)
#   tier 3  policy.rules            low / informational -> alert
#   tier 0  allowlist.rules         pass                -> never changed
#
# Policies (RULE_ACTION_POLICY):
#   detect     everything -> alert             (pure IDS; no drops at all)
#   balanced   tier1 -> drop, tier2/3 -> alert (default; block known-bad only)
#   aggressive tier1+tier2 -> drop, tier3 -> alert
#   paranoid   tier1+tier2+tier3 -> drop
#
# Additional controls:
#   --ips-mode ids   forces EVERYTHING to alert regardless of policy (safety: a
#                    passive sensor must never carry drop actions).
#   --only-sids / --except-sids   surgical include/exclude lists.
#   --classtypes      override actions for specific rule classtypes.
#   --dry-run         show what would change without writing.
#
# The script is idempotent and only rewrites the leading action token of each
# rule line, preserving the rest of the rule byte-for-byte.
# ==============================================================================
import argparse
import os
import re
import sys
from pathlib import Path

# Rule action verbs Suricata understands (rule starts with one of these).
ACTIONS = ("alert", "drop", "reject", "rejectsrc", "rejectdst", "rejectboth", "pass")
RULE_RE = re.compile(r'^\s*(#\s*)?(' + "|".join(ACTIONS) + r')\b(.*)$')
SID_RE = re.compile(r'\bsid\s*:\s*(\d+)\s*;')
CLASSTYPE_RE = re.compile(r'\bclasstype\s*:\s*([^;]+);')

# Tier -> rule files. Each tier may list several files. Tier 1 (high-confidence
# block-known-bad) includes this image's shipped rulesets — docker API malware
# and Salt Typhoon / UNC4841 C2 are all high-confidence malicious, so they drop
# under balanced+ policies. Anything not listed here is treated as the managed
# feed (classtype-driven). Extend these lists to add your own rule files.
TIER_FILES = {
    1: ["block-known-bad.rules", "docker_malware.rules", "salt_typhoon_unc4841.rules"],
    2: ["suspicious.rules"],
    3: ["policy.rules"],
}
ALLOWLIST_FILE = "allowlist.rules"

# Policy matrix: tier -> action.
POLICIES = {
    "detect":     {1: "alert", 2: "alert", 3: "alert"},
    "balanced":   {1: "drop",  2: "alert", 3: "alert"},
    "aggressive": {1: "drop",  2: "drop",  3: "alert"},
    "paranoid":   {1: "drop",  2: "drop",  3: "drop"},
}

# For the managed feed (suricata.rules) we key off classtype risk, since it has
# no tier file. High-confidence malicious classtypes default to drop in
# balanced+; everything else stays alert.
HIGH_RISK_CLASSTYPES = {
    "trojan-activity", "command-and-control", "exploit-kit",
    "shellcode-detect", "attempted-admin", "web-application-attack",
    "successful-admin", "malware-cnc",
}


def desired_action(tier, policy, classtype=None):
    if tier in POLICIES[policy]:
        return POLICIES[policy][tier]
    # Managed feed (no tier): use classtype risk.
    if classtype and classtype.strip() in HIGH_RISK_CLASSTYPES:
        return "drop" if policy in ("balanced", "aggressive", "paranoid") else "alert"
    return "alert"


def rewrite_line(line, new_action):
    """Replace only the leading action token; keep comment state and the body."""
    m = RULE_RE.match(line)
    if not m:
        return line, False
    comment, old_action, body = m.group(1) or "", m.group(2), m.group(3)
    # Never touch 'pass' rules -- those are the allowlist escape hatch.
    if old_action == "pass":
        return line, False
    if old_action == new_action:
        return line, False
    # Preserve leading whitespace and any '#'.
    leading_ws = line[:len(line) - len(line.lstrip())]
    newline = f"{leading_ws}{comment}{new_action}{body}\n"
    return newline, True


def get_sid(line):
    m = SID_RE.search(line)
    return int(m.group(1)) if m else None


def get_classtype(line):
    m = CLASSTYPE_RE.search(line)
    return m.group(1) if m else None


def process_file(path, tier, policy, ips_mode, only_sids, except_sids, dry_run):
    changed = 0
    try:
        text = path.read_text().splitlines(keepends=True)
    except OSError as e:
        print(f"[toggle] WARN: cannot read {path}: {e}", file=sys.stderr)
        return 0
    out = []
    for line in text:
        m = RULE_RE.match(line)
        if not m or (m.group(2) == "pass"):
            out.append(line)
            continue
        sid = get_sid(line)
        # Surgical scoping.
        if only_sids and (sid not in only_sids):
            out.append(line)
            continue
        if except_sids and (sid in except_sids):
            out.append(line)
            continue
        # IDS mode: force alert everywhere (a passive sensor must not drop).
        if ips_mode == "ids":
            target = "alert"
        else:
            target = desired_action(tier, policy, get_classtype(line))
        newline, did = rewrite_line(line, target)
        out.append(newline)
        changed += 1 if did else 0
    if changed and not dry_run:
        path.write_text("".join(out))
    verb = "would change" if dry_run else "changed"
    if changed:
        print(f"[toggle] {path.name}: {verb} {changed} rule action(s) "
              f"(tier={tier if tier else 'feed'}, policy={policy}, mode={ips_mode})")
    return changed


def parse_sid_list(s):
    if not s:
        return set()
    out = set()
    for part in s.replace(",", " ").split():
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def main():
    ap = argparse.ArgumentParser(description="Risk-based Suricata rule action toggler.")
    ap.add_argument("--policy", default=os.environ.get("RULE_ACTION_POLICY", "balanced"),
                    choices=list(POLICIES.keys()))
    ap.add_argument("--ips-mode", default=os.environ.get("IPS_MODE", "ids"),
                    choices=["ids", "ips"])
    ap.add_argument("--rules-dir", default="/var/lib/suricata/rules")
    ap.add_argument("--only-sids", default="", help="comma/space list: only toggle these SIDs")
    ap.add_argument("--except-sids", default="", help="comma/space list: never toggle these SIDs")
    ap.add_argument("--all-drop", action="store_true",
                    help="legacy shortcut: force policy=paranoid")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.all_drop:
        args.policy = "paranoid"

    rules_dir = Path(args.rules_dir)
    if not rules_dir.is_dir():
        print(f"[toggle] ERROR: rules dir {rules_dir} not found", file=sys.stderr)
        return 1

    only_sids = parse_sid_list(args.only_sids)
    except_sids = parse_sid_list(args.except_sids)

    print(f"[toggle] policy={args.policy} ips_mode={args.ips_mode} dir={rules_dir}"
          + (" [DRY-RUN]" if args.dry_run else ""))

    total = 0
    # Tiered operator files (each tier may map to several rule files).
    for tier, fnames in TIER_FILES.items():
        for fname in fnames:
            p = rules_dir / fname
            if p.exists():
                total += process_file(p, tier, args.policy, args.ips_mode,
                                       only_sids, except_sids, args.dry_run)
    # Managed feed (classtype-driven), if present.
    feed = rules_dir / "suricata.rules"
    if feed.exists():
        total += process_file(feed, None, args.policy, args.ips_mode,
                              only_sids, except_sids, args.dry_run)

    # allowlist.rules is intentionally never processed (pass rules only).
    print(f"[toggle] done: {total} rule action(s) {'would change' if args.dry_run else 'changed'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())