#!/usr/bin/env python3
"""Build events that a given Sigma rule must match, and prove it offline.

Testing a detection engine against data nobody labelled proves nothing: a
quiet result is indistinguishable from a broken one. This takes a rule,
constructs an event that satisfies its detection block, renders that event
in the wire format the add-ons parse, reads it back with an independent
parser, and evaluates the rule's condition against the result. Only an
event that survives that round trip is offered as ground truth.

That ordering matters. If the evaluator disagrees, the synthesiser is
wrong and nothing has been learned about Splunk. If the evaluator agrees
and Splunk does not detect it, the fault is somewhere in the Splunk path --
conversion, batching, parsing, scheduling or the summary index -- and the
test has found something real.

Sophistication tiers change how the event is placed, not whether it
matches:

  t1  on its own, repeated, with obvious indicators
  t2  inside a plausible parent/child chain
  t3  a legitimate-looking parent, one occurrence, spread through the window
  t4  a single event buried in heavy background traffic

A rule that is caught at t1 and missed at t4 is not a rule problem. It is a
statement about aggregation thresholds and search windows, which is exactly
what this is for.

    ./test/synthesize.py --rules <dir> --count 12 --tier t3 --out batch.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "pylib"))

import yaml  # noqa: E402

from importlib import util as _util  # noqa: E402
_spec = _util.spec_from_file_location("scorer", HERE / "score-dataset.py")
scorer = _util.module_from_spec(_spec)
_spec.loader.exec_module(scorer)

# Values used to pad a "contains" match. Chosen to look like ordinary path
# and argument text so the synthesised event does not stand out by being
# obviously synthetic, which would make a detection meaningless.
PAD_LEFT_WIN = ["C:\\Windows\\System32\\", "C:\\Program Files\\Contoso\\", ""]
PAD_LEFT_NIX = ["/usr/bin/", "/usr/local/bin/", ""]
PAD_LEFT = PAD_LEFT_WIN
PAD_RIGHT = ["", "", ""]

BENIGN_PARENTS = [
    "C:\\Windows\\explorer.exe",
    "C:\\Windows\\System32\\svchost.exe",
    "C:\\Windows\\System32\\services.exe",
]

# What each parent plausibly starts on a Windows host. userinit.exe starts
# the shell and stops; services.exe starts service hosts; explorer.exe
# starts what a person clicks. Pairing outside this is the kind of thing a
# rule is written to notice.
BENIGN_TREE = {
    "C:\\Windows\\System32\\userinit.exe": [
        "C:\\Windows\\explorer.exe",
    ],
    "C:\\Windows\\explorer.exe": [
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Windows\\System32\\notepad.exe",
        "C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE",
    ],
    "C:\\Windows\\System32\\services.exe": [
        "C:\\Windows\\System32\\svchost.exe",
        "C:\\Windows\\System32\\spoolsv.exe",
        "C:\\Windows\\System32\\SearchIndexer.exe",
    ],
    "C:\\Windows\\System32\\svchost.exe": [
        "C:\\Windows\\System32\\RuntimeBroker.exe",
        "C:\\Windows\\System32\\taskhostw.exe",
    ],
}
SUSPECT_PARENTS = [
    "C:\\Program Files\\Microsoft Office\\root\\Office16\\WINWORD.EXE",
    "C:\\Windows\\System32\\wbem\\WmiPrvSE.exe",
]


def satisfy(value, modifiers: List[str], rnd: random.Random,
            pads: Optional[List[str]] = None) -> Optional[str]:
    """A concrete string that satisfies one field's expectation."""
    pads = pads if pads is not None else PAD_LEFT
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    v = str(value)

    # Modifiers this cannot construct a value for. Guessing would produce a
    # test that fails for a reason unrelated to the engine.
    for unsupported in ("re", "base64", "base64offset", "cidr", "utf16", "wide"):
        if any(unsupported in m for m in modifiers):
            return None

    if "contains" in modifiers:
        return f"{rnd.choice(pads)}{v}{rnd.choice(PAD_RIGHT)}"
    if "startswith" in modifiers:
        return f"{v}{rnd.choice(PAD_RIGHT)}"
    if "endswith" in modifiers:
        return f"{rnd.choice(pads)}{v}"
    # An exact match, or a wildcard the rule wrote itself.
    return v.replace("*", "x") if "*" in v else v


def fields_from_selection(sel, rnd: random.Random,
                          pads: Optional[List[str]] = None) -> Optional[Dict[str, str]]:
    """Field values that satisfy one selection block."""
    if isinstance(sel, list):
        # A list of maps: satisfying any one of them satisfies the selection.
        for item in sel:
            got = fields_from_selection(item, rnd, pads)
            if got:
                return got
        return None
    if not isinstance(sel, dict):
        return None

    out: Dict[str, str] = {}
    for key, value in sel.items():
        parts = key.split("|")
        name, modifiers = parts[0], [p.lower() for p in parts[1:]]
        if name.startswith("|"):
            return None
        if "all" in modifiers and isinstance(value, list):
            # Every listed value must appear, so concatenate them.
            joined = " ".join(str(v).strip() for v in value if str(v).strip())
            got = satisfy(joined, [m for m in modifiers if m != "all"] or ["contains"], rnd, pads)
        else:
            got = satisfy(value, modifiers, rnd, pads)
        if got is None:
            return None
        out[name] = got
    return out


def positive_selections(detection: Dict) -> List[str]:
    """Selection names the condition requires, ignoring the filters.

    Taken from the condition text rather than from the block order: a rule
    whose condition is "selection and not filter" must have selection
    satisfied and filter avoided, and the names alone do not say which.
    """
    cond = str(detection.get("condition", ""))
    names = [k for k in detection if k != "condition"]
    wanted, negated, i = [], set(), 0
    tokens = cond.replace("(", " ( ").replace(")", " ) ").split()
    while i < len(tokens):
        t = tokens[i].lower()
        if t == "not" and i + 1 < len(tokens):
            nxt = tokens[i + 1].strip("()")
            if "*" in nxt:
                negated.update(n for n in names if n.startswith(nxt.rstrip("*")))
            else:
                negated.add(nxt)
            i += 2
            continue
        i += 1
    for n in names:
        if n in negated:
            continue
        base = n.split("_")[0].lower()
        if base in ("filter", "exclusion", "exclude") or n.lower().startswith("filter"):
            continue
        wanted.append(n)
    return wanted


def build_fields(rule: Dict, rnd: random.Random,
                 pads: Optional[List[str]] = None) -> Optional[Dict[str, str]]:
    detection = rule.get("detection") or {}
    if not detection.get("condition"):
        return None
    fields: Dict[str, str] = {}
    for name in positive_selections(detection):
        got = fields_from_selection(detection[name], rnd, pads)
        if got is None:
            return None
        fields.update(got)
    return fields or None


# ---------------------------------------------------------------- rendering

def render_sysmon(fields: Dict[str, str], when: datetime, host: str,
                  parent: str, rec: int) -> str:
    """A Sysmon process-creation event, in the shape Windows writes it.

    EventData attributes are single quoted because that is how Windows
    renders event XML, and the vendor add-on's extraction matches only that
    form.
    """
    ts = when.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    data = {
        "RuleName": "-", "UtcTime": ts,
        "ProcessGuid": "{%s}" % hashlib.md5(str(rec).encode()).hexdigest()[:32],
        "ProcessId": str(4000 + rec % 50000),
        "Image": fields.get("Image", "C:\\Windows\\System32\\cmd.exe"),
        "FileVersion": "10.0.19041.1",
        "Description": fields.get("Description", "Windows Command Processor"),
        "Product": fields.get("Product", "Microsoft Windows Operating System"),
        "Company": fields.get("Company", "Microsoft Corporation"),
        "OriginalFileName": fields.get("OriginalFileName", "Cmd.Exe"),
        "CommandLine": fields.get("CommandLine", fields.get("Image", "cmd.exe")),
        "CurrentDirectory": fields.get("CurrentDirectory", "C:\\Windows\\system32\\"),
        "User": fields.get("User", "LAB\\svc_admin"),
        "LogonGuid": "{00000000-0000-0000-0000-000000000000}",
        "LogonId": "0x3e7",
        "TerminalSessionId": "0",
        "IntegrityLevel": fields.get("IntegrityLevel", "High"),
        "Hashes": fields.get("Hashes", "MD5=" + hashlib.md5(str(rec).encode()).hexdigest()),
        "ParentProcessGuid": "{%s}" % hashlib.md5(f"p{rec}".encode()).hexdigest()[:32],
        "ParentProcessId": str(600 + rec % 400),
        "ParentImage": fields.get("ParentImage", parent),
        "ParentCommandLine": fields.get("ParentCommandLine", parent),
        "ParentUser": fields.get("ParentUser", "LAB\\svc_admin"),
    }
    # Any field the rule asked for that is not part of the standard set is
    # still written, or the rule could not match what it keyed on.
    for k, v in fields.items():
        data.setdefault(k, v)

    body = "".join(f"<Data Name='{k}'>{_xml(v)}</Data>" for k, v in data.items())
    return (
        '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
        '<System><Provider Name="Microsoft-Windows-Sysmon" '
        'Guid="{5770385f-c22a-43e0-bf4c-06f5698ffbd9}"/><EventID>1</EventID>'
        '<Version>5</Version><Level>4</Level><Task>1</Task><Opcode>0</Opcode>'
        '<Keywords>0x8000000000000000</Keywords>'
        f'<TimeCreated SystemTime="{ts}"/><EventRecordID>{rec}</EventRecordID>'
        '<Correlation/><Execution ProcessID="2104" ThreadID="3048"/>'
        '<Channel>Microsoft-Windows-Sysmon/Operational</Channel>'
        f'<Computer>{host}</Computer><Security UserID="S-1-5-18"/></System>'
        f'<EventData>{body}</EventData></Event>'
    )


def render_auditd(fields: Dict[str, str], when: datetime, host: str,
                  rec: int) -> List[str]:
    """An auditd EXECVE pair, as the Linux audit subsystem writes it."""
    ts = f"{when.timestamp():.3f}"
    # auditd puts the command and its arguments in a0..aN, which is what
    # Sigma's Linux rules key on.
    cmd = fields.get("CommandLine") or fields.get("Image") or "/bin/sh"
    argv = [a for a in str(cmd).split(" ") if a]
    for key in ("a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7"):
        if key in fields:
            idx = int(key[1:])
            while len(argv) <= idx:
                argv.append("")
            argv[idx] = fields[key]
    args = " ".join(f'a{i}="{_q(a)}"' for i, a in enumerate(argv) if a != "")
    exe = fields.get("exe") or fields.get("Image") or (argv[0] if argv else "/bin/sh")
    return [
        f"type=SYSCALL msg=audit({ts}:{rec}): arch=c000003e syscall=59 success=yes "
        f"exit=0 a0=7ffd a1=7ffe a2=7fff a3=0 items=2 ppid=939 pid={4000 + rec % 50000} "
        f"auid={fields.get('auid', '0')} uid=0 gid=0 euid={fields.get('euid', '0')} "
        f'suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=pts0 ses=1 comm="{_q(Path(exe).name)}" '
        f'exe="{_q(exe)}" key=(null)',
        f"type=EXECVE msg=audit({ts}:{rec}): argc={len([a for a in argv if a])} {args}",
    ]


def _xml(v: str) -> str:
    return (str(v).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _q(v: str) -> str:
    return str(v).replace('"', "")


# ---------------------------------------------------------------- the check

def verify(rule: Dict, rendered: str, kind: str) -> Tuple[bool, str]:
    """Parse the rendered event back and ask the evaluator if it matches.

    The round trip is the point. Rendering is where a synthesiser is most
    likely to be wrong, and a test built on an event that does not actually
    match the rule reports a detection failure that is really a test
    failure.
    """
    try:
        if kind == "windows":
            parsed = scorer.parse_winevent(rendered)
        else:
            parsed = scorer.parse_auditd(rendered)
        if not parsed:
            return False, "the rendered event did not parse"
        ok = scorer.evaluate_condition(
            str(rule["detection"]["condition"]), rule["detection"], parsed)
        return bool(ok), "" if ok else "the evaluator says it does not match"
    except KeyError as e:
        return False, f"condition references {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rules", required=True, help="Sigma rules directory")
    ap.add_argument("--count", type=int, default=10, help="rules to cover")
    ap.add_argument("--tier", default="t1", choices=("t1", "t2", "t3", "t4"))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--host", default="LAB-WIN-01")
    ap.add_argument("--linux-host", default="lab-nix-01")
    ap.add_argument("--window-minutes", type=int, default=20)
    ap.add_argument("--out", required=True, help="where to write the batch")
    args = ap.parse_args(argv)

    rnd = random.Random(args.seed)
    files = sorted(Path(args.rules).rglob("*.yml"))
    rnd.shuffle(files)

    # Volume and placement per tier. The matching event is identical; what
    # changes is how hard it is to notice.
    tier = {
        "t1": dict(repeats=5, background=200, parents=BENIGN_PARENTS + SUSPECT_PARENTS),
        "t2": dict(repeats=3, background=800, parents=SUSPECT_PARENTS),
        "t3": dict(repeats=1, background=3000, parents=BENIGN_PARENTS),
        "t4": dict(repeats=1, background=12000, parents=BENIGN_PARENTS),
    }[args.tier]

    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=args.window_minutes)

    planted, skipped, rec = [], {}, 1
    win_lines: List[str] = []
    nix_lines: List[str] = []

    for f in files:
        if len(planted) >= args.count:
            break
        try:
            rule = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        ls = rule.get("logsource") or {}
        product = (ls.get("product") or "").lower()
        category = (ls.get("category") or "").lower()
        if product == "windows" and category == "process_creation":
            kind = "windows"
        elif product == "linux":
            kind = "linux"
        else:
            skipped["log source not exercised here"] = skipped.get("log source not exercised here", 0) + 1
            continue

        pads = PAD_LEFT_WIN if kind == "windows" else PAD_LEFT_NIX
        fields = build_fields(rule, rnd, pads)
        if not fields:
            skipped["cannot construct a matching value"] = skipped.get("cannot construct a matching value", 0) + 1
            continue

        when = start + timedelta(seconds=rnd.randint(0, args.window_minutes * 60))
        parent = rnd.choice(tier["parents"])
        if kind == "windows":
            ev = render_sysmon(fields, when, args.host, parent, rec)
            ok, why = verify(rule, ev, "windows")
            lines = [ev]
        else:
            pair = render_auditd(fields, when, args.linux_host, rec)
            ok, why = verify(rule, pair[1], "linux")
            lines = pair
        if not ok:
            skipped[why] = skipped.get(why, 0) + 1
            continue

        for r in range(tier["repeats"]):
            t = when + timedelta(seconds=r * rnd.randint(5, 90))
            if kind == "windows":
                win_lines.append(render_sysmon(fields, t, args.host, parent, rec))
            else:
                nix_lines.extend(render_auditd(fields, t, args.linux_host, rec))
            rec += 1

        planted.append({
            "rule_id": rule.get("id", ""),
            "rule": rule.get("title", ""),
            "level": rule.get("level", "medium"),
            "platform": "Windows" if kind == "windows" else "Linux",
            "tier": args.tier,
            "occurrences": tier["repeats"],
            "first_seen": when.isoformat(),
            "fields": fields,
        })

    # Background: ordinary activity, and bait that looks interesting but is
    # not. Precision is only measurable against something.
    tree_parents = list(BENIGN_TREE)
    for i in range(tier["background"]):
        t = start + timedelta(seconds=rnd.randint(0, args.window_minutes * 60))
        parent = rnd.choice(tree_parents)
        img = rnd.choice(BENIGN_TREE[parent])
        # Arguments that suit the process, rather than one service command
        # line pasted onto everything.
        if img.endswith("svchost.exe"):
            cl = f"{img} -k netsvcs -p"
        elif img.endswith("chrome.exe"):
            cl = f'"{img}" --type=renderer --no-sandbox'
        elif img.endswith("explorer.exe"):
            cl = img
        else:
            cl = f"{img}"
        win_lines.append(render_sysmon(
            {"Image": img, "CommandLine": cl}, t, args.host, parent, rec))
        rec += 1
        if i % 3 == 0:
            nix_lines.extend(render_auditd(
                {"CommandLine": rnd.choice([
                    "/usr/bin/ls -la /var/log", "/bin/systemctl status sshd",
                    "/usr/sbin/cron -f", "/usr/bin/find /home -type f"])},
                t, args.linux_host, rec))
            rec += 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rnd.shuffle(win_lines)
    nix_lines_sorted = nix_lines
    (out.with_suffix(".windows.log")).write_text("\n".join(win_lines) + "\n")
    (out.with_suffix(".linux.log")).write_text("\n".join(nix_lines_sorted) + "\n")
    out.write_text(json.dumps({
        "tier": args.tier, "seed": args.seed,
        "generated": now.isoformat(),
        "window_minutes": args.window_minutes,
        "windows_events": len(win_lines), "linux_events": len(nix_lines),
        "planted": planted,
    }, indent=2))

    print(f"\n  tier {args.tier}: {len(planted)} rule(s) planted and verified")
    print(f"  {len(win_lines)} Windows event(s), {len(nix_lines)} Linux line(s)")
    print(f"  signal is {len(planted) * tier['repeats'] / max(len(win_lines), 1) * 100:.3f}% of the Windows batch")
    if skipped:
        print(f"\n  rules not usable as ground truth:")
        for why, n in sorted(skipped.items(), key=lambda kv: -kv[1])[:6]:
            print(f"    {n:5}  {why}")
    print(f"\n  {out}")
    print(f"  {out.with_suffix('.windows.log')}")
    print(f"  {out.with_suffix('.linux.log')}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
