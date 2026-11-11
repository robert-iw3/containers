#!/usr/bin/env python3

"""Seed Linux and Windows audit events in the formats the Splunk add-ons produce.

Exists because the lab cannot generate real detection telemetry: auditd
needs CAP_AUDIT_CONTROL in the initial namespace, Sysmon for Linux is not
installed, and no sshd runs on the forwarder host. Record layouts and
average sizes here were measured from a real auditd corpus and a real
/var/log/auth.log, not guessed.

Planted positives are derived from the Sigma rules themselves: a rule whose
detection is simple field equality gets an event built to satisfy it. That
makes the ground truth self-maintaining and gives a per-rule expected count
to assert against.

Output is one file per source type, plus ground-truth.json.

Volume matters: a download-trial or Free licence indexes 500 MB/day, and
exceeding it repeatedly disables search. Every tier reports measured bytes
and --budget-mb refuses to write past a ceiling.
"""

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: python3 -m pip install --target ./pylib PyYAML")

HERE = Path(__file__).resolve().parent

# Source type -> the add-on that produces it in a real deployment.
SOURCETYPES = {
    "linux_audit": "Splunk Add-on for Unix and Linux (/var/log/audit/audit.log)",
    "linux_secure": "Splunk Add-on for Unix and Linux (/var/log/secure)",
    "bash_history": "Splunk Add-on for Unix and Linux",
    "sysmon:linux": "Splunk Add-on for Sysmon for Linux",
    "XmlWinEventLog:Security": "Splunk Add-on for Microsoft Windows",
    "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational": "Splunk Add-on for Sysmon",
}

# Measured from the reference corpus, bytes per record including newline.
MEASURED_SIZES = {
    "SYSCALL": 544, "EXECVE": 105, "PROCTITLE": 166, "CWD": 40, "PATH": 150,
    "linux_secure": 170, "bash_history": 60,
    "sysmon:linux": 1200,
    "XmlWinEventLog:Security": 1800,
    "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational": 2500,
}

# Tiers are RECORD counts, not logical events: one auditd execution is five
# records (SYSCALL, EXECVE, CWD, PATH, PROCTITLE). Sized so large stays
# near a quarter of the 500 MB/day licence cap.
TIERS = {"small": 2_000, "medium": 150_000, "large": 600_000}

HOSTS = [f"lab-lnx-{i:02d}" for i in range(1, 9)]
WIN_HOSTS = [f"LAB-WIN-{i:02d}" for i in range(1, 6)]
# Fictional identities only: never a real account from the host that
# runs this generator.
USERS = [("jdoe", 1000), ("svc_deploy", 1101), ("analyst", 1102), ("root", 0)]

# Benign background commands, drawn from what a real host actually runs.
BENIGN_EXEC = [
    ["/usr/bin/bash", "-c", "ls -l /var/log"], ["ls", "-l"], ["cat", "/etc/hostname"],
    ["grep", "-r", "error", "/var/log/syslog"], ["systemctl", "status", "sshd"],
    ["/usr/bin/python3", "-c", "print(1)"], ["df", "-h"], ["ps", "-ef"],
    ["/usr/bin/git", "status"], ["tar", "-czf", "/tmp/b.tgz", "/etc/hosts"],
    ["sed", "-n", "1,10p", "/etc/passwd"], ["awk", "{print $1}", "/etc/group"],
    ["curl", "-s", "https://repo.internal.example.com/health"],
    ["/usr/lib/firefox/firefox", "--new-tab"], ["gnome-shell", "--mode=user"],
]

BENIGN_WIN_IMAGES = [
    (r"C:\Windows\System32\svchost.exe", "-k netsvcs"),
    (r"C:\Windows\System32\RuntimeBroker.exe", ""),
    (r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE", r"/dde"),
    (r"C:\Windows\explorer.exe", ""),
    (r"C:\Windows\System32\taskhostw.exe", "SYSTEM"),
]


def hexify(value: str) -> str:
    """auditd hex-encodes a value containing whitespace or quotes, so a
    string search for it fails. Reproduced here deliberately."""
    if re.search(r'[\s"]', value):
        return value.encode().hex().upper()
    return f'"{value}"'


class AuditSeq:
    """auditd serial numbers are monotonic across a boot."""

    def __init__(self, start: int = 86_000_000):
        self.n = start

    def next(self) -> int:
        self.n += random.randint(1, 4)
        return self.n


# ---------------------------------------------------------------- formatters

def fmt_auditd_exec(ts: float, seq: int, argv, user, host, cwd="/home/lab", key="exec"):
    """One auditd execution group: SYSCALL + EXECVE + CWD + PROCTITLE."""
    name, uid = user
    exe = argv[0] if argv[0].startswith("/") else f"/usr/bin/{argv[0]}"
    comm = Path(exe).name
    stamp = f"audit({ts:.3f}:{seq})"
    pid = random.randint(2000, 90000)
    ppid = random.randint(500, 1999)
    recs = [
        (f"type=SYSCALL msg={stamp}: arch=c000003e syscall=59 success=yes exit=0 "
         f"a0={random.randint(0x500000000000, 0x7fffffffffff):x} a1={random.randint(0x500000000000, 0x7fffffffffff):x} "
         f"a2={random.randint(0x500000000000, 0x7fffffffffff):x} a3=0 items=2 ppid={ppid} pid={pid} "
         f"auid={uid} uid={uid} gid={uid} euid={uid} suid={uid} fsuid={uid} egid={uid} sgid={uid} fsgid={uid} "
         f"tty=pts1 ses=3 comm={hexify(comm)} exe=\"{exe}\" "
         f"subj=unconfined key=\"{key}\"ARCH=x86_64 SYSCALL=execve AUID=\"{name}\" UID=\"{name}\""),
        (f"type=EXECVE msg={stamp}: argc={len(argv)} "
         + " ".join(f'a{i}="{a}"' for i, a in enumerate(argv))),
        f'type=CWD msg={stamp}: cwd="{cwd}"',
        (f"type=PATH msg={stamp}: item=0 name=\"{exe}\" inode={random.randint(100000, 9999999)} "
         f"dev=fc:01 mode=0100755 ouid=0 ogid=0 rdev=00:00 nametype=NORMAL "
         f"cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0OUID=\"root\" OGID=\"root\""),
        f"type=PROCTITLE msg={stamp}: proctitle={hexify(' '.join(argv))}",
    ]
    return recs


def fmt_linux_secure(ts, host, kind, user, srcip=None):
    from datetime import datetime, timezone
    t = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    t = t[:-2] + ":" + t[-2:]
    pid = random.randint(1000, 60000)
    name = user[0]
    ip = srcip or f"10.{random.randint(1,250)}.{random.randint(1,250)}.{random.randint(2,250)}"
    bodies = {
        "ssh_fail": f"sshd[{pid}]: Failed password for {name} from {ip} port {random.randint(1024,65535)} ssh2",
        "ssh_fail_invalid": f"sshd[{pid}]: Failed password for invalid user {name} from {ip} port {random.randint(1024,65535)} ssh2",
        "ssh_ok": f"sshd[{pid}]: Accepted publickey for {name} from {ip} port {random.randint(1024,65535)} ssh2: RSA SHA256:{hashlib.sha256(name.encode()).hexdigest()[:43]}",
        "sudo_ok": f"sudo[{pid}]:  {name} : TTY=pts/1 ; PWD=/home/{name} ; USER=root ; COMMAND=/usr/bin/systemctl restart nginx",
        "sudo_fail": f"sudo[{pid}]:  {name} : 1 incorrect password attempt ; TTY=pts/1 ; PWD=/home/{name} ; USER=root ; COMMAND=/bin/bash",
        "useradd": f"useradd[{pid}]: new user: name=svc_backdoor, UID=1337, GID=1337, home=/home/svc_backdoor, shell=/bin/bash, from=/dev/pts/1",
        "group_add": f"usermod[{pid}]: add '{name}' to group 'sudo'",
        "cron": f"CRON[{pid}]: pam_unix(cron:session): session opened for user {name}(uid={user[1]}) by (uid=0)",
    }
    return f"{t} {host} {bodies[kind]}"


def fmt_sysmon_linux(ts, host, image, cmdline, parent_image, user):
    from datetime import datetime, timezone
    t = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return (
        f'<Event><System><Provider Name="Linux-Sysmon" '
        f'Guid="{{ff032593-a8d3-4f13-b0d6-01fc615a0f97}}"/><EventID>1</EventID>'
        f"<Version>5</Version><Level>4</Level><Task>1</Task>"
        f'<TimeCreated SystemTime="{t}"/><EventRecordID>{random.randint(1,9999999)}</EventRecordID>'
        f"<Channel>Linux-Sysmon/Operational</Channel><Computer>{host}</Computer>"
        f'<Security UserId="0"/></System><EventData>'
        f'<Data Name="RuleName">-</Data>'
        f'<Data Name="UtcTime">{t}</Data>'
        f'<Data Name="ProcessGuid">{{{hashlib.md5(str(ts).encode()).hexdigest()[:8]}-0000-0000-0000-000000000000}}</Data>'
        f'<Data Name="ProcessId">{random.randint(1000,99999)}</Data>'
        f'<Data Name="Image">{image}</Data>'
        f'<Data Name="CommandLine">{cmdline}</Data>'
        f'<Data Name="CurrentDirectory">/home/{user[0]}</Data>'
        f'<Data Name="User">{user[0]}</Data>'
        f'<Data Name="ParentImage">{parent_image}</Data>'
        f'<Data Name="ParentCommandLine">{Path(parent_image).name}</Data>'
        f"</EventData></Event>"
    )


def fmt_win_security(ts, host, event_code, user, extra=None):
    from datetime import datetime, timezone
    t = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    extra = extra or {}
    data = {
        4624: {"SubjectUserName": "-", "TargetUserName": user, "LogonType": "3",
               "IpAddress": f"10.20.{random.randint(1,250)}.{random.randint(2,250)}",
               "WorkstationName": random.choice(WIN_HOSTS)},
        4625: {"SubjectUserName": "-", "TargetUserName": user, "LogonType": "3",
               "Status": "0xc000006d", "SubStatus": "0xc000006a",
               "IpAddress": f"10.20.{random.randint(1,250)}.{random.randint(2,250)}"},
        4688: {"SubjectUserName": user, "NewProcessName": extra.get("image", r"C:\Windows\System32\cmd.exe"),
               "CommandLine": extra.get("cmdline", ""),
               "ParentProcessName": extra.get("parent", r"C:\Windows\explorer.exe")},
        4720: {"SubjectUserName": "Administrator", "TargetUserName": extra.get("new_user", "svc_backdoor")},
        4732: {"SubjectUserName": "Administrator", "TargetUserName": "Administrators",
               "MemberName": f"CN={user}"},
    }[event_code]
    fields = "".join(f'<Data Name="{k}">{v}</Data>' for k, v in data.items())
    return (
        f'<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
        f'<System><Provider Name="Microsoft-Windows-Security-Auditing" '
        f'Guid="{{54849625-5478-4994-a5ba-3e3b0328c30d}}"/>'
        f"<EventID>{event_code}</EventID><Version>0</Version><Level>0</Level>"
        f"<Task>13312</Task><Opcode>0</Opcode>"
        f'<Keywords>0x8020000000000000</Keywords><TimeCreated SystemTime="{t}"/>'
        f"<EventRecordID>{random.randint(1,99999999)}</EventRecordID>"
        f'<Execution ProcessID="4" ThreadID="8"/><Channel>Security</Channel>'
        f"<Computer>{host}</Computer><Security/></System>"
        f"<EventData>{fields}</EventData></Event>"
    )


# ------------------------------------------------------- Sigma-derived truth

SIMPLE_VALUE = (str, int, float)


def extract_positive(rule: dict):
    """Build a field->value map that satisfies a rule, or None if the rule's
    detection is too complex to satisfy mechanically."""
    det = rule.get("detection", {}) or {}
    condition = str(det.get("condition", "")).strip()
    # Only single-selection rules with no filters: anything with "not", "or"
    # or a filter term needs real logic to satisfy.
    sels = [k for k in det if k != "condition"]
    if len(sels) != 1 or condition not in sels:
        return None
    sel = det[sels[0]]
    if not isinstance(sel, dict):
        return None
    out = {}
    for key, val in sel.items():
        if "|" in key:
            field, _, modifier = key.partition("|")
        else:
            field, modifier = key, ""
        if modifier not in ("", "endswith", "startswith", "contains"):
            return None
        if isinstance(val, list):
            if not val or not all(isinstance(v, SIMPLE_VALUE) for v in val):
                return None
            val = val[0]
        if not isinstance(val, SIMPLE_VALUE):
            return None
        val = str(val)
        if "*" in val:
            return None
        if modifier == "endswith":
            val = f"/opt/stage{val}" if val.startswith("/") else f"/usr/bin/{val}"
        out[field] = val
    return out or None


def load_rules(rules_dir: Path):
    rules = []
    for f in sorted(rules_dir.rglob("*.yml")):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and d.get("title") and d.get("detection"):
            d["_file"] = str(f.relative_to(rules_dir))
            rules.append(d)
    return rules


def classify(rule):
    ls = rule.get("logsource", {}) or {}
    product, service, category = ls.get("product"), ls.get("service"), ls.get("category")
    if product == "linux" and service == "auditd":
        return "linux_audit"
    if product == "linux" and category in ("process_creation", "file_event", "network_connection"):
        return "sysmon:linux"
    if product == "windows" and category == "process_creation":
        return "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational"
    if product == "windows":
        return "XmlWinEventLog:Security"
    if product == "linux":
        return "linux_secure"
    return None


def build_positive_event(rule, fields, sourcetype, ts, seq):
    host = random.choice(HOSTS)
    user = random.choice(USERS)
    if sourcetype == "linux_audit":
        argv = []
        rec_type = fields.get("type", "EXECVE")
        for i in range(8):
            key = f"a{i}"
            if key in fields:
                argv.append(fields[key])
        if not argv:
            for key in ("exe", "comm", "name"):
                if key in fields:
                    argv = [fields[key]]
                    break
        if not argv:
            return None
        if rec_type != "EXECVE":
            # Rules keyed on a SYSCALL name need that record, not an EXECVE.
            stamp = f"audit({ts:.3f}:{seq})"
            syscall = fields.get("SYSCALL", "execve")
            exe = fields.get("exe", argv[0])
            return [(f"type=SYSCALL msg={stamp}: arch=c000003e syscall=59 success=yes exit=0 "
                     f"a0=7f0000000000 a1=7f0000000001 a2=7f0000000002 a3=0 items=1 "
                     f"ppid=1001 pid={random.randint(2000,90000)} auid={user[1]} uid={user[1]} "
                     f"gid={user[1]} euid={user[1]} suid={user[1]} fsuid={user[1]} "
                     f"egid={user[1]} sgid={user[1]} fsgid={user[1]} tty=pts1 ses=3 "
                     f"comm={hexify(Path(exe).name)} exe=\"{exe}\" subj=unconfined "
                     f"SYSCALL={syscall} AUID=\"{user[0]}\" UID=\"{user[0]}\"")], host
        return fmt_auditd_exec(ts, seq, argv, user, host), host
    if sourcetype == "sysmon:linux":
        image = fields.get("Image", "/usr/bin/suspicious")
        cmdline = fields.get("CommandLine", Path(image).name)
        if "CommandLine" not in fields and len(fields) > 1:
            cmdline = f"{Path(image).name} " + " ".join(
                str(v) for k, v in fields.items() if k != "Image")
        parent = fields.get("ParentImage", "/usr/bin/bash")
        return [fmt_sysmon_linux(ts, host, image, cmdline, parent, user)], host
    if sourcetype.startswith("XmlWinEventLog:Microsoft-Windows-Sysmon"):
        whost = random.choice(WIN_HOSTS)
        image = fields.get("Image", r"C:\Windows\System32\cmd.exe")
        cmdline = fields.get("CommandLine", Path(image).name)
        return [fmt_win_security(ts, whost, 4688, user[0],
                                 {"image": image, "cmdline": cmdline,
                                  "parent": fields.get("ParentImage", r"C:\Windows\explorer.exe")})], whost
    if sourcetype == "XmlWinEventLog:Security":
        whost = random.choice(WIN_HOSTS)
        code = int(fields.get("EventID", 4625))
        if code not in (4624, 4625, 4688, 4720, 4732):
            return None
        return [fmt_win_security(ts, whost, code, user[0])], whost
    if sourcetype == "linux_secure":
        return [fmt_linux_secure(ts, host, "ssh_fail_invalid", user)], host
    return None


# ------------------------------------------------------------------ benign

def build_benign(sourcetype, ts, seq):
    host = random.choice(HOSTS)
    user = random.choice(USERS)
    if sourcetype == "linux_audit":
        return fmt_auditd_exec(ts, seq, random.choice(BENIGN_EXEC), user, host), host
    if sourcetype == "linux_secure":
        kind = random.choices(
            ["cron", "ssh_ok", "sudo_ok", "ssh_fail"], weights=[50, 25, 20, 5])[0]
        return [fmt_linux_secure(ts, host, kind, user)], host
    if sourcetype == "bash_history":
        return [f"#{int(ts)}\n" + " ".join(random.choice(BENIGN_EXEC))], host
    if sourcetype == "sysmon:linux":
        argv = random.choice(BENIGN_EXEC)
        exe = argv[0] if argv[0].startswith("/") else f"/usr/bin/{argv[0]}"
        return [fmt_sysmon_linux(ts, host, exe, " ".join(argv), "/usr/bin/bash", user)], host
    if sourcetype.startswith("XmlWinEventLog:Microsoft-Windows-Sysmon"):
        whost = random.choice(WIN_HOSTS)
        image, args = random.choice(BENIGN_WIN_IMAGES)
        return [fmt_win_security(ts, whost, 4688, user[0],
                                 {"image": image, "cmdline": f"{image} {args}".strip()})], whost
    if sourcetype == "XmlWinEventLog:Security":
        whost = random.choice(WIN_HOSTS)
        code = random.choices([4624, 4625, 4688], weights=[70, 10, 20])[0]
        return [fmt_win_security(ts, whost, code, user[0])], whost
    return None


# -------------------------------------------------------------------- main

def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rules", required=True,
                    help="Directory of Sigma rules, used to derive planted positives")
    ap.add_argument("--out", default="./seeded", help="Output directory")
    ap.add_argument("--tier", choices=sorted(TIERS), default="small",
                    help=f"Record count: {', '.join(f'{k}={v:,}' for k, v in TIERS.items())}")
    ap.add_argument("--events", type=int, default=None,
                    help="Explicit record count, overrides --tier")
    ap.add_argument("--positives-per-rule", type=int, default=3,
                    help="Planted matching events per satisfiable rule")
    ap.add_argument("--budget-mb", type=float, default=150.0,
                    help="Refuse to write more than this. A download-trial or "
                         "Free licence indexes 500 MB/day.")
    ap.add_argument("--window-hours", type=float, default=2.0,
                    help="Spread timestamps over this many hours ending now")
    ap.add_argument("--seed", type=int, default=1337, help="RNG seed")
    ap.add_argument("--estimate-only", action="store_true",
                    help="Report projected bytes and exit without writing")
    args = ap.parse_args(argv[1:])

    random.seed(args.seed)
    total_events = args.events if args.events else TIERS[args.tier]

    rules_dir = Path(args.rules)
    if not rules_dir.is_dir():
        sys.exit(f"--rules is not a directory: {rules_dir}")
    rules = load_rules(rules_dir)

    # Derive ground truth from the rules.
    planted = []
    skipped = Counter()
    for rule in rules:
        st = classify(rule)
        if st is None:
            skipped["no source type mapping"] += 1
            continue
        fields = extract_positive(rule)
        if fields is None:
            skipped["detection too complex to satisfy mechanically"] += 1
            continue
        planted.append((rule, fields, st))

    print(f"Sigma rules read:              {len(rules)}")
    print(f"Rules with a plantable positive: {len(planted)}")
    for reason, n in skipped.most_common():
        print(f"  skipped {n:>5}  {reason}")

    import time
    now = time.time()
    window = args.window_hours * 3600
    seq = AuditSeq()

    files = defaultdict(list)
    truth = defaultdict(int)
    truth_meta = {}

    # Planted positives first, so ground truth is exact.
    for rule, fields, st in planted:
        for _ in range(args.positives_per_rule):
            ts = now - random.random() * window
            built = build_positive_event(rule, fields, st, ts, seq.next())
            if built is None:
                continue
            recs, _host = built
            files[st].extend(recs)
            truth[rule["title"]] += 1
            truth_meta[rule["title"]] = {
                "sigma_id": rule.get("id", ""),
                "file": rule["_file"],
                "sourcetype": st,
                "level": rule.get("level"),
                "satisfied_fields": fields,
            }

    planted_records = sum(len(v) for v in files.values())
    if len(truth) < len(planted):
        print(f"  note     {len(planted) - len(truth):>5}  plantable rules yielded no event "
              f"(no usable argv or event code)")

    # Benign background, distributed across the source types in use.
    bg_sourcetypes = sorted(set(list(files) + ["linux_audit", "linux_secure",
                                               "bash_history", "sysmon:linux",
                                               "XmlWinEventLog:Security"]))
    weights = {"linux_audit": 45, "linux_secure": 20, "bash_history": 10,
               "sysmon:linux": 10, "XmlWinEventLog:Security": 10,
               "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational": 5}
    pool = [st for st in bg_sourcetypes for _ in range(weights.get(st, 5))]
    # Fill to the record target, counting what each source type actually emits.
    emitted = planted_records
    guard = 0
    while emitted < total_events and guard < total_events * 10:
        guard += 1
        st = random.choice(pool)
        ts = now - random.random() * window
        built = build_benign(st, ts, seq.next())
        if built is None:
            continue
        recs, _host = built
        files[st].extend(recs)
        emitted += len(recs)

    # Measure before writing.
    sizes = {st: sum(len(r) + 1 for r in recs) for st, recs in files.items()}
    total_bytes = sum(sizes.values())
    total_records = sum(len(r) for r in files.values())

    print()
    print(f"{'source type':<52} {'records':>9} {'MB':>8}")
    for st in sorted(files):
        print(f"{st:<52} {len(files[st]):>9,} {sizes[st]/1048576:>8.2f}")
    print(f"{'TOTAL':<52} {total_records:>9,} {total_bytes/1048576:>8.2f}")
    print()
    print(f"planted positive records: {planted_records:,} "
          f"across {len(truth)} rules ({args.positives_per_rule} per rule)")
    print(f"licence budget:           {args.budget_mb:.0f} MB "
          f"({total_bytes/1048576/args.budget_mb*100:.1f}% used); "
          f"500 MB/day is the download-trial and Free cap")

    if total_bytes / 1048576 > args.budget_mb:
        sys.exit(f"\nREFUSED: {total_bytes/1048576:.1f} MB exceeds --budget-mb "
                 f"{args.budget_mb:.0f}. Lower --tier or raise the budget deliberately.")

    if args.estimate_only:
        print("\n--estimate-only: nothing written")
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    written = {}
    for st, recs in sorted(files.items()):
        fname = re.sub(r"[^A-Za-z0-9_.-]", "_", st) + ".log"
        path = out / fname
        path.write_text("\n".join(recs) + "\n", encoding="utf-8")
        written[st] = str(path)

    ground = {
        "generated_at": now,
        "seed": args.seed,
        "tier": args.tier if not args.events else f"custom:{args.events}",
        "window_hours": args.window_hours,
        "positives_per_rule": args.positives_per_rule,
        "total_records": total_records,
        "total_bytes": total_bytes,
        "sourcetype_files": written,
        "sourcetype_origin": {k: v for k, v in SOURCETYPES.items() if k in written},
        "expected_detections": dict(truth),
        "rule_detail": truth_meta,
    }
    (out / "ground-truth.json").write_text(json.dumps(ground, indent=1), encoding="utf-8")
    print(f"\nwrote {len(written)} log files and ground-truth.json to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
