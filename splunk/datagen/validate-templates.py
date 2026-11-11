#!/usr/bin/env python3

"""Validate datagen templates before any data is emitted.

A typo in a template does not usually fail loudly. An unknown transform name,
a placeholder referring to a variable that was renamed, a generator parameter
spelled wrong: each produces output that looks plausible and is wrong. By
the time that data is indexed, the cost of finding out is a reindex.

So this runs first, and datagen refuses to emit while any error stands.

Checks, in order:

  1. JSON parses, with the line and column of a syntax error
  2. required keys exist and have the right types
  3. every generator name is known, with a suggestion for a near miss
  4. generator parameters are the ones that generator reads
  5. every placeholder resolves to a variable defined for that record
  6. every transform in a chain is known
  7. no two templates share a name or an output file
  8. one record group from each template renders without raising

The generator, transform, and timestamp format lists are imported from
datagen rather than restated here. Two copies drift, and a validator that
has drifted approves templates that fail at emit time.

  validate-templates.py                      # validate ./templates
  validate-templates.py --templates ./mine
  validate-templates.py --strict             # warnings fail too
"""

import argparse
import difflib
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_datagen():
    """Import datagen for its authoritative lists and its renderer."""
    path = HERE / "datagen.py"
    if not path.exists():
        sys.exit(f"datagen.py not found beside this script ({HERE})")
    spec = importlib.util.spec_from_file_location("datagen", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DG = load_datagen()

REQUIRED = {"name": str, "sourcetype": str, "records": list}
OPTIONAL = {
    "origin": str, "notes": str, "output_file": str, "weight": int,
    "variables": dict, "avg_bytes": int, "description": str,
}


class Problem:
    __slots__ = ("severity", "file", "where", "message", "hint")

    def __init__(self, severity, file, where, message, hint=""):
        self.severity = severity
        self.file = file
        self.where = where
        self.message = message
        self.hint = hint

    def __str__(self):
        line = f"{self.severity:<7} {self.file}"
        if self.where:
            line += f" [{self.where}]"
        line += f"\n        {self.message}"
        if self.hint:
            line += f"\n        hint: {self.hint}"
        return line


def suggest(name, known):
    """Name a likely intended value for a near miss. A typo is far more
    common than a genuinely unknown generator."""
    close = difflib.get_close_matches(str(name), sorted(known), n=2, cutoff=0.6)
    if close:
        return "did you mean " + " or ".join(repr(c) for c in close) + "?"
    return "known values: " + ", ".join(sorted(known))


def validate_file(path: Path, problems: list, seen_names: dict, seen_out: dict):
    rel = path.name
    raw = path.read_text(encoding="utf-8", errors="replace")

    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        problems.append(Problem(
            "ERROR", rel, f"line {e.lineno}, column {e.colno}",
            f"invalid JSON: {e.msg}",
            "a trailing comma, an unescaped backslash, or a missing quote"))
        return
    if not isinstance(doc, dict):
        problems.append(Problem("ERROR", rel, "", "template must be a JSON object"))
        return

    for key, kind in REQUIRED.items():
        if key not in doc:
            problems.append(Problem("ERROR", rel, "", f"missing required key {key!r}",
                                    suggest(key, list(doc)) if doc else ""))
        elif not isinstance(doc[key], kind):
            problems.append(Problem(
                "ERROR", rel, key,
                f"{key!r} must be {kind.__name__}, got {type(doc[key]).__name__}"))

    for key, value in doc.items():
        if key.startswith("_"):
            continue
        if key in REQUIRED or key in OPTIONAL:
            kind = REQUIRED.get(key) or OPTIONAL.get(key)
            if not isinstance(value, kind) and not (kind is int and isinstance(value, bool) is False and isinstance(value, int)):
                problems.append(Problem("ERROR", rel, key,
                                        f"{key!r} must be {kind.__name__}"))
        else:
            problems.append(Problem(
                "WARNING", rel, key, f"unrecognized top-level key {key!r}; it is ignored",
                suggest(key, set(REQUIRED) | set(OPTIONAL))))

    if "records" not in doc or not isinstance(doc["records"], list):
        return
    if not doc["records"]:
        problems.append(Problem("ERROR", rel, "records", "'records' must not be empty"))
        return

    name = doc.get("name")
    if isinstance(name, str):
        if name in seen_names:
            problems.append(Problem(
                "ERROR", rel, "name",
                f"template name {name!r} already used by {seen_names[name]}",
                "names must be unique: --only selects by name"))
        else:
            seen_names[name] = rel
    out = doc.get("output_file") or (
        re.sub(r"[^A-Za-z0-9_.-]", "_", str(doc.get("sourcetype", ""))) + ".log")
    if out in seen_out:
        problems.append(Problem(
            "ERROR", rel, "output_file",
            f"output file {out!r} already used by {seen_out[out]}",
            "two templates writing one file interleave their records"))
    else:
        seen_out[out] = rel

    def check_variables(varmap, where):
        if not isinstance(varmap, dict):
            problems.append(Problem("ERROR", rel, where, "'variables' must be an object"))
            return
        for vname, spec in varmap.items():
            vwhere = f"{where}.{vname}"
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", vname):
                problems.append(Problem(
                    "ERROR", rel, vwhere,
                    f"variable name {vname!r} is not usable in a placeholder",
                    "letters, digits and underscore only, not starting with a digit"))
            if not isinstance(spec, dict):
                problems.append(Problem("ERROR", rel, vwhere,
                                        "a variable must be an object"))
                continue
            gen = spec.get("gen", "const")
            if gen not in DG.GENERATORS:
                problems.append(Problem("ERROR", rel, vwhere,
                                        f"unknown generator {gen!r}",
                                        suggest(gen, DG.GENERATORS)))
                continue
            allowed = DG.GENERATOR_PARAMS.get(gen, set()) | {"gen"}
            for pkey in spec:
                if pkey not in allowed and not pkey.startswith("_"):
                    problems.append(Problem(
                        "WARNING", rel, vwhere,
                        f"{gen!r} does not read {pkey!r}; it is ignored",
                        suggest(pkey, allowed - {"gen"}) if allowed - {"gen"}
                        else f"{gen!r} takes no parameters"))
            if gen == "choice":
                vals = spec.get("values")
                if not isinstance(vals, list) or not vals:
                    problems.append(Problem("ERROR", rel, vwhere,
                                            "'choice' needs a non-empty 'values' list"))
                elif "weights" in spec:
                    w = spec["weights"]
                    if not isinstance(w, list) or len(w) != len(vals):
                        problems.append(Problem(
                            "ERROR", rel, vwhere,
                            f"'weights' has {len(w) if isinstance(w, list) else '?'} "
                            f"entries but 'values' has {len(vals)}"))
                    elif any(not isinstance(x, (int, float)) or x < 0 for x in w):
                        problems.append(Problem("ERROR", rel, vwhere,
                                                "'weights' must be non-negative numbers"))
            if gen == "timestamp":
                fmt = spec.get("format", "iso8601")
                if fmt not in DG.TIMESTAMP_FORMATS:
                    problems.append(Problem("ERROR", rel, vwhere,
                                            f"unknown timestamp format {fmt!r}",
                                            suggest(fmt, DG.TIMESTAMP_FORMATS)))
                elif fmt == "strftime" and "pattern" not in spec:
                    problems.append(Problem("WARNING", rel, vwhere,
                                            "'strftime' without 'pattern' uses a default"))
            if gen in ("int", "float"):
                lo, hi = spec.get("min", 0), spec.get("max", 100 if gen == "int" else 1.0)
                if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi:
                    problems.append(Problem("ERROR", rel, vwhere,
                                            f"min {lo} is greater than max {hi}"))
            if gen == "sha256_of":
                ref = spec.get("of")
                if not ref:
                    problems.append(Problem("ERROR", rel, vwhere,
                                            "'sha256_of' needs 'of', the variable to hash"))
            if gen == "hex":
                w = spec.get("width", 12)
                if not isinstance(w, int) or w < 1:
                    problems.append(Problem("ERROR", rel, vwhere,
                                            "'width' must be a positive integer"))

    tpl_vars = doc.get("variables", {}) or {}
    check_variables(tpl_vars, "variables")

    for i, rec in enumerate(doc["records"]):
        rwhere = f"records[{i}]"
        if not isinstance(rec, dict):
            problems.append(Problem("ERROR", rel, rwhere, "a record must be an object"))
            continue
        for rkey in rec:
            if rkey not in ("weight", "lines", "variables") and not rkey.startswith("_"):
                problems.append(Problem("WARNING", rel, f"{rwhere}.{rkey}",
                                        f"unrecognized record key {rkey!r}; it is ignored",
                                        suggest(rkey, {"weight", "lines", "variables"})))
        if "weight" in rec and (not isinstance(rec["weight"], int)
                                or isinstance(rec["weight"], bool)
                                or rec["weight"] < 1):
            problems.append(Problem("ERROR", rel, f"{rwhere}.weight",
                                    "'weight' must be an integer of 1 or more"))
        rec_vars = rec.get("variables", {}) or {}
        if rec_vars:
            check_variables(rec_vars, f"{rwhere}.variables")
        defined = set(tpl_vars) | set(rec_vars)

        lines = rec.get("lines")
        if not isinstance(lines, list) or not lines:
            problems.append(Problem("ERROR", rel, f"{rwhere}.lines",
                                    "'lines' must be a non-empty list"))
            continue
        for j, line in enumerate(lines):
            lwhere = f"{rwhere}.lines[{j}]"
            if not isinstance(line, str):
                problems.append(Problem("ERROR", rel, lwhere, "each line must be a string"))
                continue
            # The typo catcher: a placeholder naming a variable that does not
            # exist raises at emit time, after other records are written.
            for m in DG.PLACEHOLDER.finditer(line):
                vname, chain = m.group(1), m.group(2)
                if vname not in defined:
                    problems.append(Problem(
                        "ERROR", rel, lwhere,
                        f"placeholder {{{vname}}} is not a defined variable",
                        suggest(vname, defined) if defined
                        else "this record has no variables defined"))
                for step in [t for t in chain.split("|") if t]:
                    if step not in DG.TRANSFORMS:
                        problems.append(Problem(
                            "ERROR", rel, lwhere,
                            f"unknown transform {step!r} on {{{vname}}}",
                            suggest(step, DG.TRANSFORMS)))
            # A brace sequence that looks like a placeholder but did not
            # parse as one is a typo. Literal braces are common in real event
            # data -- Windows provider GUIDs, JSON payloads -- so only
            # placeholder-shaped text is reported.
            bare = re.sub(DG.PLACEHOLDER.pattern, "", line)
            for m in re.finditer(r"\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\|[^}]*)?\s*\}", bare):
                problems.append(Problem(
                    "ERROR", rel, lwhere,
                    f"{m.group(0)!r} looks like a placeholder but did not parse",
                    "a transform chain may be malformed: use "
                    "{name|transform}, lower case, no spaces"))
            for m in re.finditer(r"\{([A-Za-z_][A-Za-z0-9_]*)\s*$", bare):
                problems.append(Problem(
                    "ERROR", rel, lwhere,
                    f"unclosed placeholder {{{m.group(1)}",
                    "a closing brace is missing"))


def dry_render(path: Path, problems: list):
    """Render one group from each record so anything the static checks missed
    surfaces here rather than part-way through a run."""
    rel = path.name
    try:
        templates = DG.load_templates(path)
    except SystemExit as e:
        problems.append(Problem("ERROR", rel, "", f"template would not load: {e}"))
        return
    import random
    from datetime import datetime, timezone
    rng = random.Random(0)
    for t in templates:
        for i, rec in enumerate(t["records"]):
            single = dict(t)
            single["records"] = [rec]
            try:
                DG.emit_once(single, rng, {}, datetime.now(timezone.utc), 3600.0)
            except Exception as e:
                problems.append(Problem(
                    "ERROR", rel, f"records[{i}]",
                    f"rendering raised {type(e).__name__}: {e}",
                    "the static checks did not catch this; the record cannot be emitted"))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--templates", default=str(HERE / "templates"),
                    help="Template directory or a single .json file")
    ap.add_argument("--strict", action="store_true",
                    help="Treat warnings as failures")
    ap.add_argument("--quiet", action="store_true",
                    help="Print only the summary line")
    args = ap.parse_args(argv[1:])

    root = Path(args.templates)
    if root.is_dir():
        files = sorted(f for f in root.glob("*.json") if f.name != "manifest.json")
    elif root.is_file():
        files = [root]
    else:
        sys.exit(f"no such template path: {root}")
    if not files:
        sys.exit(f"no .json templates found in {root}")

    problems, seen_names, seen_out = [], {}, {}
    for f in files:
        before = len(problems)
        validate_file(f, problems, seen_names, seen_out)
        # Only render a file that passed its static checks; rendering a
        # structurally broken template just reports the same fault twice.
        if not any(p.severity == "ERROR" for p in problems[before:]):
            dry_render(f, problems)

    errors = [p for p in problems if p.severity == "ERROR"]
    warnings = [p for p in problems if p.severity == "WARNING"]

    if not args.quiet:
        for p in problems:
            print(p)
        if problems:
            print()

    print(f"{len(files)} template(s): {len(errors)} error(s), {len(warnings)} warning(s)")
    if errors:
        return 1
    if warnings and args.strict:
        print("--strict: warnings treated as failures")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
