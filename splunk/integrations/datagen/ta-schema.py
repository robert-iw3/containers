#!/usr/bin/env python3

"""Extract the field schema a Splunk add-on declares, per source type.

Reads an add-on's own configuration and reports, for each source type, every
field it tries to produce and where that field comes from. The point is to
generate test data from what the add-on expects rather than from guesswork:
an event that exercises every declared extraction tests the whole parsing
path, and an add-on's props.conf is the only authoritative statement of what
that path is.

Where each field comes from, named as Splunk names them:

  extracted   field extraction (EXTRACT-), a search-time regex over _raw
  reported    field transform (REPORT-), a transforms.conf stanza
  aliased     field alias (FIELDALIAS-)
  evaluated   calculated field (EVAL-), plus the fields its eval reads
  lookup      automatic lookup (LOOKUP-), its match and output fields
  auto        automatic key/value extraction, governed by KV_MODE

Only extractions, transforms, and the inputs the other three read have to
exist in the raw event. The rest are knowledge objects applied on top, so a
generator that emits the raw inputs gets them for free. That is the reason
for separating them here.

Standard library only.

  ta-schema.py --ta /path/to/Splunk_TA_nix
  ta-schema.py --ta /path/to/Splunk_TA_windows --sourcetype 'XmlWinEventLog:Security'
  ta-schema.py --ta ... --json schema.json --min-fields 5
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Named capture groups, both syntaxes Splunk accepts.
CAPTURE = re.compile(r"\(\?P?<([A-Za-z_][A-Za-z0-9_.]*)>")
# FORMAT = field::$1 or $1::$2
FORMAT_FIELD = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)::")
# Identifiers inside an EVAL expression.
IDENT = re.compile(r"(?<![\w'\"])([A-Za-z_][A-Za-z0-9_.]{1,60})(?![\w(])")

# SPL functions and literals that look like fields but are not.
SPL_WORDS = {
    "if", "case", "coalesce", "isnull", "isnotnull", "null", "true", "false",
    "like", "match", "replace", "substr", "strftime", "strptime", "tostring",
    "tonumber", "mvappend", "mvjoin", "mvindex", "mvcount", "mvfilter",
    "split", "len", "lower", "upper", "trim", "ltrim", "rtrim", "round",
    "floor", "ceiling", "abs", "max", "min", "now", "relative_time",
    "searchmatch", "cidrmatch", "validate", "nullif", "in", "and", "or",
    "not", "xor", "AND", "OR", "NOT", "IN", "md5", "sha1", "sha256",
    "urldecode", "spath", "json_extract", "printf", "typeof", "exact",
}


def parse_conf(path: Path):
    """Parse a Splunk .conf file into {stanza: {key: value}}.

    Handles trailing-backslash continuations and comments. Later keys in a
    stanza win, which is what Splunk does within one file.
    """
    out = defaultdict(dict)
    if not path.exists():
        return out
    cur = None
    pending_key = None
    pending_val = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip("\n")
        if pending_key is not None:
            stripped = line.rstrip()
            if stripped.endswith("\\"):
                pending_val.append(stripped[:-1])
                continue
            pending_val.append(stripped)
            if cur is not None:
                out[cur][pending_key] = "".join(pending_val).strip()
            pending_key, pending_val = None, []
            continue
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1]
            out.setdefault(cur, {})
            continue
        if "=" not in s or cur is None:
            continue
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip()
        if line.rstrip().endswith("\\"):
            pending_key, pending_val = k, [v[:-1] if v.endswith("\\") else v]
            continue
        out[cur][k] = v
    return out


def eval_inputs(expr: str):
    """Fields an EVAL expression reads. Quoted 'field' references in Splunk
    EVAL are field names, so they count; double-quoted strings are literals."""
    fields = set()
    for m in re.finditer(r"'([A-Za-z_][A-Za-z0-9_.]*)'", expr):
        fields.add(m.group(1))
    # Strip string literals before scanning bare identifiers.
    stripped = re.sub(r'"[^"]*"', '""', expr)
    stripped = re.sub(r"'[^']*'", "''", stripped)
    for m in IDENT.finditer(stripped):
        name = m.group(1)
        if name in SPL_WORDS or name.lower() in SPL_WORDS:
            continue
        if name.isdigit():
            continue
        fields.add(name)
    return fields


def transform_fields(tname: str, transforms):
    """Fields a transforms.conf stanza produces, and whether it writes an
    index-time field."""
    st = transforms.get(tname)
    if st is None:
        return set(), {}
    produced = set()
    regex = st.get("REGEX", "")
    produced |= set(CAPTURE.findall(regex))
    fmt = st.get("FORMAT", "")
    if fmt:
        produced |= {f for f in FORMAT_FIELD.findall(fmt)}
    meta = {
        "source_key": st.get("SOURCE_KEY", ""),
        "writes_meta": st.get("WRITE_META", "").lower() == "true",
        "has_regex": bool(regex),
        "delims": st.get("DELIMS", ""),
        "declared_fields": st.get("FIELDS", ""),
    }
    if meta["declared_fields"]:
        produced |= {f.strip().strip('"') for f in meta["declared_fields"].split(",") if f.strip()}
    return produced, meta


def cim_tags(sourcetype, eventtypes, tags):
    """CIM data models a source type reaches, via eventtypes and tags.

    An eventtype search naming the source type, whose eventtype carries CIM
    tags, is how an add-on declares data model membership.
    """
    models = set()
    ets = set()
    for et_name, et in eventtypes.items():
        search = et.get("search", "")
        if not search:
            continue
        if (f'"{sourcetype}"' in search or f"sourcetype={sourcetype}" in search
                or f"sourcetype = {sourcetype}" in search
                or re.search(rf"\b{re.escape(sourcetype)}\b", search)):
            ets.add(et_name)
    for et_name in ets:
        tagstanza = tags.get(f"eventtype={et_name}", {})
        for tag, state in tagstanza.items():
            if str(state).lower() == "enabled":
                models.add(tag)
    return sorted(models), sorted(ets)


def analyze(ta_dir: Path):
    default = ta_dir / "default"
    props = parse_conf(default / "props.conf")
    transforms = parse_conf(default / "transforms.conf")
    eventtypes = parse_conf(default / "eventtypes.conf")
    tags = parse_conf(default / "tags.conf")

    schema = {}
    for stanza, keys in props.items():
        # source:: and host:: stanzas assign a source type rather than
        # describing one, so they are reported separately.
        kind = "sourcetype"
        if stanza.startswith(("source::", "host::")):
            kind = "assignment"
        entry = {
            "kind": kind,
            "wildcard": any(c in stanza for c in "*()"),
            "extracted": set(), "reported": set(), "aliased": {},
            "evaluated": {}, "lookup_in": set(), "lookup_out": set(),
            "raw_required": set(), "derived": set(),
            "kv_mode": keys.get("KV_MODE", ""),
            "rename": keys.get("rename", ""),
            "indexed_extractions": keys.get("INDEXED_EXTRACTIONS", ""),
            "assigns_sourcetype": keys.get("sourcetype", ""),
            "transforms_used": [], "report_meta": {},
            "line_breaker": keys.get("LINE_BREAKER", ""),
            "should_linemerge": keys.get("SHOULD_LINEMERGE", ""),
            "time_prefix": keys.get("TIME_PREFIX", ""),
        }
        for k, v in keys.items():
            if k.startswith("EXTRACT-"):
                entry["extracted"] |= set(CAPTURE.findall(v))
            elif k.startswith("REPORT-"):
                for tname in [t.strip() for t in v.split(",") if t.strip()]:
                    entry["transforms_used"].append(tname)
                    produced, meta = transform_fields(tname, transforms)
                    entry["reported"] |= produced
                    if meta:
                        entry["report_meta"][tname] = meta
            elif k.startswith("FIELDALIAS-"):
                for m in re.finditer(
                        r'"?([A-Za-z_][\w.]*)"?\s+ASNEW\s+"?([A-Za-z_][\w.]*)"?'
                        r'|"?([A-Za-z_][\w.]*)"?\s+AS\s+"?([A-Za-z_][\w.]*)"?',
                        v, re.IGNORECASE):
                    src = m.group(1) or m.group(3)
                    dst = m.group(2) or m.group(4)
                    if src and dst:
                        entry["aliased"][dst] = src
            elif k.startswith("EVAL-"):
                target = k[len("EVAL-"):]
                entry["evaluated"][target] = sorted(eval_inputs(v))
            elif k.startswith("LOOKUP-"):
                parts = v.split()
                if parts:
                    rest = parts[1:]
                    out_idx = next((i for i, p in enumerate(rest)
                                    if p.upper() in ("OUTPUT", "OUTPUTNEW")), None)
                    # A lookup clause may comma-join its fields and may use
                    # AS to rename them, so split on both and drop keywords.
                    def lk(tokens):
                        names = set()
                        for tok in tokens:
                            for part in re.split(r"[,\s]+", tok):
                                part = part.strip().strip('"')
                                if not part or part.upper() in (
                                        "AS", "OUTPUT", "OUTPUTNEW"):
                                    continue
                                if re.match(r"^[A-Za-z_][A-Za-z0-9_.]*$", part):
                                    names.add(part)
                        return names
                    if out_idx is None:
                        entry["lookup_in"] |= lk(rest)
                    else:
                        entry["lookup_in"] |= lk(rest[:out_idx])
                        entry["lookup_out"] |= lk(rest[out_idx + 1:])

        # What must be in the raw event versus what Splunk derives.
        entry["derived"] = (set(entry["aliased"]) | set(entry["evaluated"])
                            | entry["lookup_out"])
        raw = set(entry["extracted"]) | set(entry["reported"])
        raw |= set(entry["aliased"].values())
        for inputs in entry["evaluated"].values():
            raw |= set(inputs)
        raw |= entry["lookup_in"]
        entry["raw_required"] = raw - entry["derived"]

        if kind == "sourcetype":
            tags_found, ets = cim_tags(stanza, eventtypes, tags)
            entry["cim_tags"] = tags_found
            entry["eventtypes"] = ets
        else:
            entry["cim_tags"] = []
            entry["eventtypes"] = []
        schema[stanza] = entry
    return schema


def jsonable(entry):
    out = {}
    for k, v in entry.items():
        out[k] = sorted(v) if isinstance(v, set) else v
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ta", required=True, action="append",
                    help="Path to an extracted add-on directory; repeatable")
    ap.add_argument("--sourcetype", default=None,
                    help="Report one source type in full")
    ap.add_argument("--min-fields", type=int, default=1,
                    help="Hide source types declaring fewer raw fields than this")
    ap.add_argument("--json", default=None, help="Write the full schema here")
    ap.add_argument("--assignments", action="store_true",
                    help="Also list source:: stanzas that assign a source type")
    args = ap.parse_args(argv[1:])

    def stanza_matches(pattern, sourcetype):
        """Does a wildcard props stanza apply to this source type? Splunk
        allows a leading (::){0} marker and * wildcards."""
        pat = pattern
        if pat.startswith("(::){0}"):
            pat = pat[len("(::){0}"):]
        pat = pat.replace(r"\S+", "*")
        if "*" not in pat:
            return False
        rx = "^" + ".*".join(re.escape(part) for part in pat.split("*")) + "$"
        return re.match(rx, sourcetype) is not None

    combined = {}
    for ta in args.ta:
        d = Path(ta)
        if not (d / "default").is_dir():
            sys.exit(f"not an add-on directory (no default/): {d}")
        name = d.name
        sch = analyze(d)
        for st, entry in sch.items():
            entry["add_on"] = name
            combined.setdefault(st, entry)
        print(f"{name}: {len(sch)} props stanzas")

    if args.sourcetype:
        entry = combined.get(args.sourcetype)
        if entry is not None:
            # Follow rename first: a renamed source type takes its
            # search-time configuration from the target stanza, and a search
            # against the original name matches nothing at all.
            chain = []
            seen = {args.sourcetype}
            cur = entry
            while cur.get("rename") and cur["rename"] not in seen:
                target = cur["rename"]
                chain.append(target)
                seen.add(target)
                nxt = combined.get(target)
                if nxt is None:
                    break
                for key in ("extracted", "reported", "raw_required", "derived",
                            "lookup_in", "lookup_out"):
                    entry[key] = set(entry[key]) | set(nxt[key])
                entry["aliased"] = {**nxt["aliased"], **entry["aliased"]}
                entry["evaluated"] = {**nxt["evaluated"], **entry["evaluated"]}
                entry["transforms_used"] = (list(nxt["transforms_used"])
                                            + list(entry["transforms_used"]))
                entry["cim_tags"] = sorted(set(entry["cim_tags"]) | set(nxt["cim_tags"]))
                if not entry["kv_mode"]:
                    entry["kv_mode"] = nxt["kv_mode"]
                if not entry["indexed_extractions"]:
                    entry["indexed_extractions"] = nxt["indexed_extractions"]
                cur = nxt
            entry["rename_chain"] = chain

            # Merge in every wildcard stanza that also applies.
            inherited = []
            for st, other in combined.items():
                if other["wildcard"] and stanza_matches(st, args.sourcetype):
                    inherited.append(st)
                    for key in ("extracted", "reported", "raw_required", "derived",
                                "lookup_in", "lookup_out"):
                        entry[key] = set(entry[key]) | set(other[key])
                    entry["aliased"] = {**other["aliased"], **entry["aliased"]}
                    entry["evaluated"] = {**other["evaluated"], **entry["evaluated"]}
                    entry["transforms_used"] = (list(other["transforms_used"])
                                                + list(entry["transforms_used"]))
                    if not entry["kv_mode"]:
                        entry["kv_mode"] = other["kv_mode"]
            entry["inherits_from"] = inherited
        if entry is None:
            matches = [s for s in combined if args.sourcetype.lower() in s.lower()]
            sys.exit(f"source type not found. Close matches: {matches[:10]}")
        print(f"\n=== {args.sourcetype}  ({entry['add_on']}) ===")
        print(f"KV_MODE          {entry['kv_mode'] or '(unset -> auto)'}")
        if entry.get("rename_chain"):
            print(f"RENAMED TO       {' -> '.join(entry['rename_chain'])}")
            print(f"                 search this name, not "
                  f"{args.sourcetype!r}, or nothing matches")
        if entry.get("indexed_extractions"):
            print(f"INDEXED_EXTRACT  {entry['indexed_extractions']} "
                  f"(index-time field extraction, so there are no "
                  f"search-time extractions to read)")
        print(f"LINE_BREAKER     {entry['line_breaker'] or '(default)'}")
        print(f"TIME_PREFIX      {entry['time_prefix'] or '(default)'}")
        print(f"CIM tags         {', '.join(entry['cim_tags']) or '(none)'}")
        print(f"\nRaw event must carry {len(entry['raw_required'])} field(s):")
        for f in sorted(entry["raw_required"]):
            print(f"    {f}")
        print(f"\nApplied by the add-on's knowledge objects ({len(entry['derived'])}):")
        for f in sorted(entry["derived"]):
            how = ("field alias of " + entry["aliased"][f]) if f in entry["aliased"] else \
                  ("calculated from " + ", ".join(entry["evaluated"][f]) if f in entry["evaluated"]
                   else "automatic lookup output")
            print(f"    {f:<28} {how}")
        if entry.get("inherits_from"):
            print(f"\nInherits from wildcard stanza(s): "
                  f"{', '.join(entry['inherits_from'])}")
        if entry["transforms_used"]:
            print(f"\nTransforms: {', '.join(entry['transforms_used'][:12])}")
        return 0

    rows = [(st, e) for st, e in combined.items()
            if e["kind"] == "sourcetype" and not e["wildcard"]
            and len(e["raw_required"]) >= args.min_fields]
    rows.sort(key=lambda x: -len(x[1]["raw_required"]))

    renames = {st: e["rename"] for st, e in combined.items() if e.get("rename")}
    if renames:
        print(f"\n{len(renames)} source type(s) are renamed at search time; "
              f"searching the original name matches nothing:")
        for st, to in sorted(renames.items())[:8]:
            print(f"  {st:<58} -> {to}")
        if len(renames) > 8:
            print(f"  ... {len(renames)-8} more")

    print(f"\n{'source type':<62} {'raw':>4} {'applied':>8}  CIM tags")
    for st, e in rows[:60]:
        tagstr = ",".join(e["cim_tags"][:3])
        print(f"{st:<62} {len(e['raw_required']):>4} {len(e['derived']):>8}  {tagstr}")
    print(f"\n{len(rows)} source types declare at least {args.min_fields} raw field(s)")

    wild = [s for s, e in combined.items() if e["wildcard"] and e["kind"] == "sourcetype"]
    if wild:
        print(f"\n{len(wild)} wildcard stanza(s) apply to many source types: "
              f"{', '.join(wild[:5])}")

    if args.assignments:
        asg = [(s, e["assigns_sourcetype"]) for s, e in combined.items()
               if e["kind"] == "assignment" and e["assigns_sourcetype"]]
        print(f"\n{len(asg)} source:: stanza(s) assign a source type:")
        for s, st in sorted(asg)[:30]:
            print(f"  {s:<58} -> {st}")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {st: jsonable(e) for st, e in combined.items()}, indent=1),
            encoding="utf-8")
        print(f"\nschema: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
