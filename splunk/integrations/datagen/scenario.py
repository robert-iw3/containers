#!/usr/bin/env python3

"""Emit labelled attack and false-positive scenarios alongside benign noise.

A generator that only produces plausible log volume cannot tell you whether a
detection works. For that the data has to contain known activity, labelled,
mixed into enough ordinary traffic that finding it is not trivial. Then
precision and recall are measurable rather than eyeballed.

Three kinds of content:

  baseline          ordinary day-to-day activity, drawn from the templates
  false_positive    legitimate activity that looks malicious: an
                    administrator using remote execution, a backup agent
                    reading everything, an authenticated vulnerability scan.
                    This is what separates a usable detection from a noisy
                    one, and it is the part most test data leaves out.
  true_positive     real attack behavior, graded by how much effort the
                    adversary spent on not being caught

Tiers, because a detection that only catches tier 1 is not the same product
as one that catches tier 4:

  1  script kiddie      default tooling, original filenames, no cleanup
  2  commodity crime    a known kill chain run end to end at speed
  3  skilled operator   living off the land, renamed binaries, logs cleared
  4  patient intrusion  valid accounts, low volume, long dwell, nothing
                        with a signature

Ground truth is written beside the data: every instance with its label,
tier, ATT&CK techniques, severity, and the field values that identify its
events, so a scorer can find them without a marker field polluting the
events. Pass --mark-events to add one anyway when convenience matters more
than realism.

Standard library only.

  scenario.py --list
  scenario.py --dataset datasets/soc-validation.json --out ./out
  scenario.py --only t1_rdp_bruteforce --instances 3 --out ./out
"""

import argparse
import hashlib
import importlib.util
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_datagen():
    spec = importlib.util.spec_from_file_location("datagen", HERE / "datagen.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DG = load_datagen()

LABELS = ("true_positive", "false_positive", "baseline")
LEVELS = ("informational", "low", "medium", "high", "critical")
TIER_NAMES = {
    0: "benign",
    1: "script kiddie",
    2: "commodity crimeware",
    3: "skilled operator",
    4: "patient intrusion",
}


# --------------------------------------------------------------- loading

def load_scenarios(path: Path):
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    out = []
    for f in files:
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"{f}: invalid JSON at line {e.lineno} column {e.colno}: {e.msg}")
        s["_file"] = str(f)
        out.append(s)
    return out


def validate_scenario(s, templates_by_name, problems):
    """Check a scenario before anything is emitted, for the same reason
    templates are checked: a step naming a template that does not exist
    produces a dataset with a silent hole in it."""
    where = Path(s.get("_file", "?")).name
    for key in ("name", "label", "steps"):
        if key not in s:
            problems.append(f"{where}: missing required key {key!r}")
    if s.get("label") not in LABELS:
        problems.append(f"{where}: label must be one of {LABELS}, got {s.get('label')!r}")
    if s.get("level") and s["level"] not in LEVELS:
        problems.append(f"{where}: level must be one of {LEVELS}, got {s['level']!r}")
    tier = s.get("tier", 0)
    if not isinstance(tier, int) or tier not in TIER_NAMES:
        problems.append(f"{where}: tier must be one of {sorted(TIER_NAMES)}, got {tier!r}")
    if s.get("label") == "true_positive" and tier == 0:
        problems.append(f"{where}: a true_positive needs a tier of 1 or more")
    steps = s.get("steps") or []
    if not isinstance(steps, list) or not steps:
        problems.append(f"{where}: steps must be a non-empty list")
        return
    for i, st in enumerate(steps):
        if not isinstance(st, dict):
            problems.append(f"{where}: steps[{i}] must be an object")
            continue
        tname = st.get("template")
        if tname not in templates_by_name:
            problems.append(
                f"{where}: steps[{i}] names template {tname!r}, which is not "
                f"loaded. Available: {', '.join(sorted(templates_by_name))}")
            continue
        tpl = templates_by_name[tname]
        ridx = st.get("record", 0)
        if not isinstance(ridx, int) or not (0 <= ridx < len(tpl["records"])):
            problems.append(
                f"{where}: steps[{i}] record {ridx!r} is out of range for "
                f"{tname} ({len(tpl['records'])} record(s))")
            continue
        # An override naming a variable the template does not define is
        # silently ignored by the renderer, so it is caught here.
        known = set(tpl.get("variables", {})) | set(
            tpl["records"][ridx].get("variables", {})) | set(s.get("variables", {}))
        for vname in (st.get("set") or {}):
            if vname not in known:
                problems.append(
                    f"{where}: steps[{i}] sets {vname!r}, which {tname} "
                    f"record {ridx} does not define. Known: "
                    f"{', '.join(sorted(known)) or '(none)'}")


# --------------------------------------------------------------- rendering

def render_step(template, record_index, overrides, scenario_vars, rng,
                seq_state, when):
    """Render one step's lines.

    Variables resolve in order: the template's own, then the scenario's
    shared ones, then the step's literal overrides. Scenario variables are
    resolved once per instance by the caller, so every step in a campaign
    agrees on host, account and process identity.
    """
    rec = template["records"][record_index]
    ctx = {"__now": when, "__offset": 0.0}
    specs = dict(template.get("variables", {}))
    specs.update(rec.get("variables", {}))
    for name, spec in specs.items():
        if name in scenario_vars or name in overrides:
            continue
        s = dict(spec)
        s["_name"] = f"{template['name']}.{name}"
        ctx[name] = DG.Gen(s, rng, seq_state).value(ctx)
    ctx.update(scenario_vars)
    ctx.update(overrides)
    return [DG.render(line, ctx) for line in rec["lines"]], ctx


def instantiate(scenario, templates_by_name, rng, seq_state, now, window_seconds):
    """Emit one occurrence of a scenario. Returns (events, truth)."""
    # Shared identity for the whole campaign, so its steps hang together.
    shared = {}
    for name, spec in (scenario.get("variables") or {}).items():
        s = dict(spec)
        s["_name"] = f"{scenario['name']}.{name}"
        shared[name] = DG.Gen(s, rng, seq_state).value(
            {"__now": now, "__offset": 0.0})

    cadence = scenario.get("cadence") or {}
    spread = float(cadence.get("spread_seconds", 300))
    jitter = float(cadence.get("jitter", 0.25))
    # Where in the available window this occurrence starts.
    start_offset = rng.random() * max(0.0, window_seconds - spread)
    base = now - timedelta(seconds=window_seconds) + timedelta(seconds=start_offset)

    events = []
    identifiers = defaultdict(set)
    digests = []
    steps = scenario["steps"]
    for i, st in enumerate(steps):
        tpl = templates_by_name[st["template"]]
        ridx = st.get("record", 0)
        repeat = int(st.get("repeat", 1))
        # A step's position in the chain, unless it names its own offset.
        if "offset_seconds" in st:
            step_at = float(st["offset_seconds"])
        else:
            step_at = spread * (i / max(1, len(steps) - 1)) if len(steps) > 1 else 0.0
        for r in range(repeat):
            drift = rng.uniform(-jitter, jitter) * spread / max(1, len(steps))
            at = base + timedelta(seconds=step_at + drift
                                  + r * float(st.get("repeat_gap_seconds", 1.0)))
            overrides = st.get("set") or {}
            lines, ctx = render_step(tpl, ridx, overrides, shared,
                                     rng, seq_state, at)
            for line in lines:
                events.append((tpl["sourcetype"], line))
                digests.append(hashlib.sha1(line.encode()).hexdigest()[:16])
            # Only values the scenario set, from its shared variables or the
            # step's overrides. A per-step random value differs on every
            # event, so recording it as an identifier would send a scorer
            # looking for something that does not identify anything.
            for key in set(shared) | set(overrides):
                val = ctx.get(key)
                if isinstance(val, (str, int, float)):
                    identifiers[key].add(str(val))
                elif isinstance(val, list):
                    identifiers[key].add(" ".join(str(x) for x in val))

    truth = {
        "scenario": scenario["name"],
        "label": scenario["label"],
        "tier": scenario.get("tier", 0),
        "tier_name": TIER_NAMES.get(scenario.get("tier", 0), "unknown"),
        "level": scenario.get("level", "medium"),
        "attack": scenario.get("attack", []),
        "description": scenario.get("description", ""),
        "detectable_as": scenario.get("detectable_as", ""),
        "why_hard": scenario.get("why_hard", ""),
        "events": len(events),
        "sourcetypes": sorted({st for st, _ in events}),
        "window_start": base.isoformat(),
        "window_end": (base + timedelta(seconds=spread)).isoformat(),
        "identifiers": {k: sorted(v) for k, v in identifiers.items()},
        # Exact attribution. A scorer matches an event to this instance by
        # the digest of its line, so a hit is never credited to the wrong
        # instance and never missed because identifiers span steps.
        "event_sha1": digests,
    }
    return events, truth


# ------------------------------------------------------------------- main

def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--templates", default=str(HERE / "templates"))
    ap.add_argument("--scenarios", default=str(HERE / "scenarios"))
    ap.add_argument("--dataset", default=None,
                    help="A dataset file composing baseline volume and scenario counts")
    ap.add_argument("--only", action="append", default=None,
                    help="Emit just this scenario; repeatable")
    ap.add_argument("--instances", type=int, default=1,
                    help="Occurrences of each --only scenario")
    ap.add_argument("--baseline-records", type=int, default=0,
                    help="Benign records to mix in around the scenarios")
    ap.add_argument("--window-hours", type=float, default=24.0,
                    help="Spread everything over this many hours ending now")
    ap.add_argument("--out", default="./scenario-out")
    ap.add_argument("--index", default="main")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--mark-events", action="store_true",
                    help="Append a datagen_scenario field to planted events. "
                         "Easier to score, less realistic: a detection must "
                         "not be allowed to key on it.")
    ap.add_argument("--budget-mb", type=float, default=150.0)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--estimate-only", action="store_true")
    args = ap.parse_args(argv[1:])

    templates = DG.load_templates(Path(args.templates))
    templates_by_name = {t["name"]: t for t in templates}
    scenarios = load_scenarios(Path(args.scenarios))
    by_name = {s["name"]: s for s in scenarios if "name" in s}

    problems = []
    for s in scenarios:
        validate_scenario(s, templates_by_name, problems)
    if problems:
        print(f"{len(problems)} problem(s) in the scenario library:\n")
        for p in problems:
            print(f"  {p}")
        print("\nRefusing to emit: a scenario with a broken step leaves a "
              "silent hole in the dataset.", file=sys.stderr)
        return 1

    if args.list:
        print(f"{'scenario':<34} {'label':<15} {'tier':<20} {'level':<9} ATT&CK")
        for s in sorted(scenarios, key=lambda x: (x.get("label", ""), x.get("tier", 0), x["name"])):
            print(f"{s['name']:<34} {s['label']:<15} "
                  f"{TIER_NAMES.get(s.get('tier', 0), '?'):<20} "
                  f"{s.get('level', '-'):<9} {','.join(s.get('attack', [])) or '-'}")
        print(f"\n{len(scenarios)} scenario(s), {len(templates)} template(s) available")
        return 0

    plan = []
    baseline_records = args.baseline_records
    if args.dataset:
        ds = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
        baseline_records = int((ds.get("baseline") or {}).get("records", 0))
        baseline_templates = (ds.get("baseline") or {}).get("templates")
        for item in ds.get("scenarios", []):
            name = item.get("scenario")
            if name not in by_name:
                sys.exit(f"{args.dataset}: unknown scenario {name!r}")
            plan.append((by_name[name], int(item.get("instances", 1))))
        if baseline_templates:
            missing = [t for t in baseline_templates if t not in templates_by_name]
            if missing:
                sys.exit(f"{args.dataset}: unknown baseline template(s): {missing}")
            templates = [t for t in templates if t["name"] in set(baseline_templates)]
    elif args.only:
        for name in args.only:
            if name not in by_name:
                sys.exit(f"unknown scenario {name!r}; --list shows them")
            plan.append((by_name[name], args.instances))
    else:
        plan = [(s, 1) for s in scenarios]

    rng = random.Random(args.seed)
    seq_state = {}
    now = datetime.now(timezone.utc)
    window = args.window_hours * 3600

    buffers = defaultdict(list)
    truths = []
    for scenario, count in plan:
        for _ in range(count):
            events, truth = instantiate(scenario, templates_by_name, rng,
                                        seq_state, now, window)
            tag = f' datagen_scenario="{scenario["name"]}"' if args.mark_events else ""
            for st, line in events:
                buffers[st].append(line + tag)
            truths.append(truth)

    planted = sum(len(v) for v in buffers.values())

    # Benign volume around the scenarios, so finding the planted activity is
    # not trivial. Without it a detection scores perfectly on anything.
    if baseline_records > 0 and templates:
        pool = [t for t in templates for _ in range(max(1, int(t.get("weight", 10))))]
        emitted = 0
        guard = 0
        while emitted < baseline_records and guard < baseline_records * 20 + 1000:
            guard += 1
            t = rng.choice(pool)
            lines = DG.emit_once(t, rng, seq_state, now, window)
            buffers[t["sourcetype"]].extend(lines)
            emitted += len(lines)

    total = sum(len(v) for v in buffers.values())
    sizes = {st: sum(len(l) + 1 for l in lines) for st, lines in buffers.items()}
    total_bytes = sum(sizes.values())

    print(f"{'source type':<52} {'records':>9} {'MB':>8}")
    for st in sorted(buffers):
        print(f"{st:<52} {len(buffers[st]):>9,} {sizes[st]/1048576:>8.2f}")
    print(f"{'TOTAL':<52} {total:>9,} {total_bytes/1048576:>8.2f}")

    lab = Counter(t["label"] for t in truths)
    tiers = Counter(t["tier"] for t in truths)
    print(f"\n{len(truths)} scenario instance(s), {planted:,} planted record(s), "
          f"{total - planted:,} baseline")
    print(f"  by label: {dict(lab)}")
    print(f"  by tier:  " + ", ".join(
        f"{k} {TIER_NAMES[k]}={v}" for k, v in sorted(tiers.items())))
    ratio = (planted / total * 100) if total else 0
    print(f"  planted activity is {ratio:.2f}% of the data")
    if ratio > 20:
        print("  NOTE: that is a high share. Real intrusions are a small "
              "fraction of traffic, and a detection tuned against a dataset "
              "this dense will be noisy in production. Raise the baseline.")
    print(f"\nbudget {args.budget_mb:.0f} MB, "
          f"{total_bytes/1048576/args.budget_mb*100:.1f}% used")
    if total_bytes / 1048576 > args.budget_mb:
        sys.exit(f"\nREFUSED: {total_bytes/1048576:.1f} MB exceeds "
                 f"--budget-mb {args.budget_mb:.0f}")
    if args.estimate_only:
        print("\n--estimate-only: nothing written")
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    written = {}
    for st, lines in sorted(buffers.items()):
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", st) + ".log"
        (out / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        written[st] = name

    ground = {
        "generated_at": now.isoformat(),
        "seed": args.seed,
        "window_hours": args.window_hours,
        "index": args.index,
        "marked_events": bool(args.mark_events),
        "total_records": total,
        "planted_records": planted,
        "baseline_records": total - planted,
        "files": written,
        "scoring": {
            "note": "An instance is detected if an alert covers its window on "
                    "its identifiers. Count true_positive instances detected "
                    "for recall, and alerts on false_positive or baseline "
                    "activity as false positives for precision.",
            "instances_by_label": dict(lab),
        },
        "instances": truths,
    }
    (out / "ground-truth.json").write_text(json.dumps(ground, indent=1),
                                           encoding="utf-8")
    print(f"\nwrote {len(written)} log file(s) and ground-truth.json to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
