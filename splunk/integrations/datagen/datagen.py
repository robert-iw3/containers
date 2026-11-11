#!/usr/bin/env python3

"""Template-driven Splunk event generator. Python 3 standard library only.

Generates realistic log data for any Splunk instance: dashboard development,
app testing, detection validation, load testing. Knows nothing about Sigma or
any other consumer.

No third-party packages. Templates are JSON because JSON is the only format
both Python 3 and Windows PowerShell 5.1 parse natively with zero
dependencies, so datagen.ps1 reads the same template files.

Volume matters on a metered license: a download-trial or Free license indexes
500 MB/day and repeatedly exceeding it disables search. Every run measures
bytes before writing and --budget-mb refuses to go past a ceiling.

  datagen.py --templates templates --tier medium --out ./out
  datagen.py --templates templates --list
  datagen.py --templates templates --tier large --estimate-only
"""

import argparse
import hashlib
import json
import random
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Record counts, not logical events: one auditd execution is five records.
TIERS = {"tiny": 200, "small": 2_000, "medium": 150_000, "large": 600_000}

PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)((?:\|[a-z_0-9]+)*)\}")

# Authoritative for both the generator and the validator, which imports
# them. Two copies of these lists drift, and a validator that has drifted
# approves templates that fail at emit time.
GENERATORS = frozenset({
    "const", "choice", "int", "float", "hex", "ipv4", "uuid", "guid_braced",
    "sequence", "timestamp", "sha256_of", "compose",
})

TIMESTAMP_FORMATS = frozenset({
    "epoch", "epoch_ms3", "iso8601", "iso8601_z", "syslog_rfc3164",
    "win_xml", "strftime",
})

# Parameters each generator reads. Used to flag a key that will be ignored,
# which is how a typo in a template silently changes the output.
GENERATOR_PARAMS = {
    "const": {"value"},
    "choice": {"values", "weights"},
    "int": {"min", "max"},
    "float": {"min", "max", "places"},
    "hex": {"width"},
    "ipv4": {"prefix"},
    "uuid": set(),
    "guid_braced": set(),
    "sequence": {"start", "step", "jitter"},
    "timestamp": {"format", "pattern"},
    "sha256_of": {"of", "length"},
    "compose": {"value"},
}


# ------------------------------------------------------------- generators

class Gen:
    """Resolves one template variable. Kept deliberately small so the
    PowerShell port stays a faithful mirror."""

    def __init__(self, spec, rng, seq_state):
        self.spec = spec
        self.rng = rng
        self.seq_state = seq_state
        self.kind = spec.get("gen", "const")

    def value(self, ctx):
        k = self.kind
        s = self.spec
        if k == "const":
            return s.get("value", "")
        if k == "choice":
            values = s["values"]
            weights = s.get("weights")
            if weights:
                return self.rng.choices(values, weights=weights, k=1)[0]
            return self.rng.choice(values)
        if k == "int":
            return self.rng.randint(int(s.get("min", 0)), int(s.get("max", 100)))
        if k == "float":
            lo, hi = float(s.get("min", 0.0)), float(s.get("max", 1.0))
            return round(self.rng.uniform(lo, hi), int(s.get("places", 2)))
        if k == "hex":
            width = int(s.get("width", 12))
            return "".join(self.rng.choice("0123456789abcdef") for _ in range(width))
        if k == "ipv4":
            prefix = s.get("prefix", "10")
            octets = [o for o in str(prefix).split(".") if o != ""]
            while len(octets) < 4:
                octets.append(str(self.rng.randint(1, 254)))
            return ".".join(octets[:4])
        if k == "uuid":
            return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
        if k == "guid_braced":
            return "{" + str(uuid.UUID(int=self.rng.getrandbits(128), version=4)) + "}"
        if k == "sequence":
            name = s.get("_name", "seq")
            step = int(s.get("step", 1))
            jitter = int(s.get("jitter", 0))
            cur = self.seq_state.get(name, int(s.get("start", 1)))
            nxt = cur + step + (self.rng.randint(0, jitter) if jitter else 0)
            self.seq_state[name] = nxt
            return cur
        if k == "timestamp":
            return self._timestamp(ctx)
        if k == "sha256_of":
            src = str(ctx.get(s.get("of", ""), ""))
            digest = hashlib.sha256(src.encode()).hexdigest()
            return digest[: int(s.get("length", 64))]
        if k == "compose":
            return render(s.get("value", ""), ctx)
        raise ValueError(f"unknown generator: {k}")

    def _timestamp(self, ctx):
        base = ctx["__now"] - timedelta(seconds=ctx["__offset"])
        fmt = self.spec.get("format", "iso8601")
        if fmt == "epoch":
            return str(int(base.timestamp()))
        if fmt == "epoch_ms3":
            return f"{base.timestamp():.3f}"
        if fmt == "iso8601":
            return base.strftime("%Y-%m-%dT%H:%M:%S.%f%z").replace("+0000", "+00:00")
        if fmt == "iso8601_z":
            return base.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        if fmt == "syslog_rfc3164":
            return base.strftime("%b %e %H:%M:%S")
        if fmt == "win_xml":
            return base.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        if fmt == "strftime":
            return base.strftime(self.spec.get("pattern", "%Y-%m-%d %H:%M:%S"))
        raise ValueError(f"unknown timestamp format: {fmt}")


# -------------------------------------------------------------- transforms

def hexify(value):
    """auditd hex-encodes any value containing whitespace or a quote, so a
    plain string search for it fails. Reproduced deliberately."""
    text = str(value)
    if re.search(r'[\s"]', text):
        return text.encode().hex().upper()
    return f'"{text}"'


def audit_args(value):
    """A list becomes auditd EXECVE argument fields: a0="x" a1="y"."""
    items = value if isinstance(value, list) else [value]
    return " ".join(f'a{i}="{v}"' for i, v in enumerate(items))


def xml_escape(value):
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


TRANSFORMS = {
    "hexify": hexify,
    "audit_args": audit_args,
    "argc": lambda v: str(len(v) if isinstance(v, list) else 1),
    "join": lambda v: " ".join(str(x) for x in v) if isinstance(v, list) else str(v),
    "join_comma": lambda v: ",".join(str(x) for x in v) if isinstance(v, list) else str(v),
    "first": lambda v: str(v[0]) if isinstance(v, list) and v else str(v),
    "basename": lambda v: str(v).replace("\\", "/").rstrip("/").split("/")[-1],
    "dirname": lambda v: "/".join(str(v).replace("\\", "/").split("/")[:-1]) or "/",
    "upper": lambda v: str(v).upper(),
    "lower": lambda v: str(v).lower(),
    "xml": xml_escape,
    "abspath": lambda v: str(v) if str(v).startswith(("/", "C:", "\\")) else f"/usr/bin/{v}",
}


def render(line, ctx):
    """Substitute {var} and {var|transform|transform} against the context."""
    def sub(match):
        name, chain = match.group(1), match.group(2)
        if name not in ctx:
            raise KeyError(f"template references undefined variable: {name}")
        value = ctx[name]
        for step in [t for t in chain.split("|") if t]:
            fn = TRANSFORMS.get(step)
            if fn is None:
                raise KeyError(f"unknown transform: {step}")
            value = fn(value)
        return str(value)
    return PLACEHOLDER.sub(sub, line)


# --------------------------------------------------------------- templates

REQUIRED_KEYS = ("name", "sourcetype", "records")


def load_templates(path: Path):
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    templates = []
    for f in files:
        if f.name == "manifest.json":
            continue
        try:
            t = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"{f}: invalid JSON: {e}")
        missing = [k for k in REQUIRED_KEYS if k not in t]
        if missing:
            sys.exit(f"{f}: template missing required key(s): {', '.join(missing)}")
        if not isinstance(t["records"], list) or not t["records"]:
            sys.exit(f"{f}: 'records' must be a non-empty list")
        for i, rec in enumerate(t["records"]):
            if "lines" not in rec or not isinstance(rec["lines"], list):
                sys.exit(f"{f}: records[{i}] needs a 'lines' list")
        t["_file"] = str(f)
        t.setdefault("output_file", re.sub(r"[^A-Za-z0-9_.-]", "_", t["sourcetype"]) + ".log")
        t.setdefault("weight", 10)
        templates.append(t)
    if not templates:
        sys.exit(f"no templates found in {path}")
    return templates


def emit_once(template, rng, seq_state, now, window_seconds):
    """Draw one record group. Variables resolve once per group so every line
    in the group agrees (an auditd audit() id, a process GUID)."""
    records = template["records"]
    weights = [r.get("weight", 10) for r in records]
    rec = rng.choices(records, weights=weights, k=1)[0]

    ctx = {"__now": now, "__offset": rng.random() * window_seconds}
    variables = dict(template.get("variables", {}))
    variables.update(rec.get("variables", {}))
    # Ordered so a compose or sha256_of can depend on an earlier variable.
    for name, spec in variables.items():
        spec = dict(spec)
        spec["_name"] = f"{template['name']}.{name}"
        ctx[name] = Gen(spec, rng, seq_state).value(ctx)
    return [render(line, ctx) for line in rec["lines"]]


def main(argv):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--templates", default=str(HERE / "templates"),
                    help="Template directory or a single .json template")
    ap.add_argument("--out", default="./datagen-out", help="Output directory")
    ap.add_argument("--tier", choices=list(TIERS), default="small",
                    help="Record count: " + ", ".join(f"{k}={v:,}" for k, v in TIERS.items()))
    ap.add_argument("--records", type=int, default=None,
                    help="Explicit record count, overrides --tier")
    ap.add_argument("--only", action="append", default=None,
                    help="Restrict to this template name; repeatable")
    ap.add_argument("--window-hours", type=float, default=2.0,
                    help="Spread timestamps over this many hours ending now")
    ap.add_argument("--budget-mb", type=float, default=150.0,
                    help="Refuse to write more than this many MB. "
                         "A download-trial or Free license indexes 500 MB/day.")
    ap.add_argument("--seed", type=int, default=None,
                    help="RNG seed. Pair with --now-epoch for byte-identical output; "
                         "on its own the wall clock still moves the timestamps.")
    ap.add_argument("--now-epoch", type=float, default=None,
                    help="Pin the clock to this epoch instead of now, so a seeded "
                         "run is reproducible. Tests rely on this.")
    ap.add_argument("--index", default="main",
                    help="Index named in the generated inputs.conf snippet")
    ap.add_argument("--estimate-only", action="store_true",
                    help="Report projected volume and exit without writing")
    ap.add_argument("--list", action="store_true",
                    help="List templates and exit")
    ap.add_argument("--skip-validate", action="store_true",
                    help="Emit without validating the templates first. "
                         "Off by default: a typo in a template produces "
                         "plausible, wrong data rather than an error.")
    args = ap.parse_args(argv[1:])

    if not args.skip_validate and not args.list:
        import subprocess
        validator = HERE / "validate-templates.py"
        if validator.exists():
            rc = subprocess.run([sys.executable, str(validator),
                                 "--templates", args.templates]).returncode
            if rc != 0:
                print("\nRefusing to emit while a template has errors. "
                      "Fix them, or pass --skip-validate.", file=sys.stderr)
                return rc
            print()

    templates = load_templates(Path(args.templates))
    if args.only:
        wanted = set(args.only)
        templates = [t for t in templates if t["name"] in wanted]
        if not templates:
            sys.exit(f"no template matched --only {sorted(wanted)}")

    if args.list:
        print(f"{'name':<24} {'sourcetype':<52} {'wt':>3}  origin")
        for t in templates:
            print(f"{t['name']:<24} {t['sourcetype']:<52} {t.get('weight', 10):>3}  "
                  f"{t.get('origin', '-')}")
        return 0

    target = args.records if args.records else TIERS[args.tier]
    rng = random.Random(args.seed)
    seq_state = {}
    now = (datetime.fromtimestamp(args.now_epoch, tz=timezone.utc)
           if args.now_epoch is not None else datetime.now(timezone.utc))
    window = args.window_hours * 3600

    pool = [t for t in templates for _ in range(max(1, int(t.get("weight", 10))))]
    buffers = {t["name"]: [] for t in templates}

    emitted = 0
    guard = 0
    while emitted < target and guard < target * 20 + 1000:
        guard += 1
        t = rng.choice(pool)
        lines = emit_once(t, rng, seq_state, now, window)
        buffers[t["name"]].extend(lines)
        emitted += len(lines)

    by_name = {t["name"]: t for t in templates}
    sizes = {n: sum(len(l) + 1 for l in lines) for n, lines in buffers.items()}
    total_bytes = sum(sizes.values())
    total_records = sum(len(v) for v in buffers.values())

    print(f"{'template':<24} {'sourcetype':<52} {'records':>9} {'MB':>8}")
    for n in sorted(buffers):
        if not buffers[n]:
            continue
        print(f"{n:<24} {by_name[n]['sourcetype']:<52} "
              f"{len(buffers[n]):>9,} {sizes[n]/1048576:>8.2f}")
    print(f"{'TOTAL':<24} {'':<52} {total_records:>9,} {total_bytes/1048576:>8.2f}")
    pct = total_bytes / 1048576 / args.budget_mb * 100 if args.budget_mb else 0
    print(f"\nbudget {args.budget_mb:.0f} MB, {pct:.1f}% used. "
          f"500 MB/day is the download-trial and Free license cap.")

    if args.budget_mb and total_bytes / 1048576 > args.budget_mb:
        sys.exit(f"\nREFUSED: {total_bytes/1048576:.1f} MB exceeds --budget-mb "
                 f"{args.budget_mb:.0f}. Lower --tier or raise the budget deliberately.")

    if args.estimate_only:
        print("\n--estimate-only: nothing written")
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    written = {}
    for n, lines in sorted(buffers.items()):
        if not lines:
            continue
        path = out / by_name[n]["output_file"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written[n] = {"path": str(path), "file": path.name,
                      "sourcetype": by_name[n]["sourcetype"],
                      "records": len(lines), "bytes": sizes[n],
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    manifest = {
        "generated_at": now.isoformat(),
        "generator": "datagen.py",
        "seed": args.seed,
        "tier": args.tier if not args.records else f"custom:{args.records}",
        "window_hours": args.window_hours,
        "total_records": total_records,
        "total_bytes": total_bytes,
        "index": args.index,
        "outputs": written,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    # A ready inputs.conf so the data can be collected without hand-editing.
    stanzas = ["# Generated by datagen.py. Point a forwarder at these files.",
               "# Paths are where the data was written; adjust if you move it."]
    for n, info in sorted(written.items()):
        stanzas += [
            f"\n[monitor://{info['path']}]",
            f"sourcetype = {info['sourcetype']}",
            f"index = {args.index}",
            "disabled = 0",
            "crcSalt = <SOURCE>",
        ]
    (out / "inputs.conf").write_text("\n".join(stanzas) + "\n", encoding="utf-8")

    print(f"\nwrote {len(written)} log files, manifest.json and inputs.conf to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
