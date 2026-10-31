"""
Linux hosts: auditd, /var/log/secure, journald, AIDE and the audit-function state.

Supersedes linux_audit.py, which labelled auditd records as linux_secure and
emitted a single SYSCALL line with no PATH, CWD or PROCTITLE - a shape that
parses in a lab and produces nonsense on a real host.

One auditd event is several lines sharing one audit id, so records from this
module carry embedded newlines. emit_environment.py escapes newlines before it
writes, which destroys the multi-line reassembly this family exists to
demonstrate; use main() below, or teach the driver to honour MULTILINE.

Registering this module is not a one-file change. sources/__init__.py must
import it and drop linux_audit, emit_environment.host_for() must map KEY to
environment.LINUX, and the driver must call reset() after harness.calibrate().
Each of those is listed in the onboarding notes; skipping any one of them fails
quietly rather than loudly.
"""

import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

try:
    import environment
except ImportError:                                   # standalone run, not through the driver
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import environment

KEY = "linux_hosts"
# The family spans six sourcetypes; this is the dominant one and the fallback
# for a driver that ignores the per-record override in meta.
SOURCETYPE = "linux:audit"
SOURCE = "/var/log/audit/audit.log"
# Share of environment BYTES. linux_audit.py declares 0.7 and the registered
# modules already sum to 100, so adopting this module means removing that 0.7
# and taking the remaining 3.3 off the other sources; nothing in the tree
# enforces the sum, so it has to be done by hand.
SHARE = 4.0
MULTILINE = True

# sourcetype -> (published source, index). The lab writes one file per
# sourcetype and the forwarder's inputs.conf binds each to the index the
# consuming macros expect.
STREAMS = {
    "linux:audit":       ("/var/log/audit/audit.log", "linux"),
    "linux_secure":      ("/var/log/secure", "linux"),
    "linux:journald":    ("journald://system", "linux"),
    "aide:report":       ("/var/log/aide/aide-check.log", "linux_fim"),
    "aide:status":       ("/var/log/aide/aide-status.log", "linux_fim"),
    "linux:audit_state": ("/var/log/aide/audit-state.log", "linux_fim"),
}

# Control evidence is matched by string presence in _raw rather than on one
# indexed field, because this family spans free text, key=value and JSON. Every
# token below is prefixed (type=, key=, event=) so the match cannot drift onto
# ordinary content.
CONTROL_FIELD = None

CONTROLS = [
    ("AU-3",     "CSF PR.PS-04", ["type=SYSCALL", "type=EXECVE", "type=CWD", "type=PATH"], True,
     "content of audit records; one group carries what, when, where, source, outcome and identity"),
    ("AU-3(1)",  "CSF PR.PS-04", ["type=EXECVE", "type=PROCTITLE"], True,
     "argv and proctitle, which exist only while the execve rule is loaded"),
    ("AU-10",    "CSF PR.AA-05", ["type=LOGIN"], True,
     "auid bound once at login, which every other attribution claim rests on"),
    ("AC-6(9)",  "CSF PR.AA-05", ["type=USER_CMD"], True,
     "use of privileged functions, with requester, command and outcome"),
    ("AC-6(10)", "CSF PR.AA-05", ["user NOT in sudoers"], True,
     "refused escalation; enforcement witnessed in operation"),
    ("AC-2(4)",  "CSF PR.AA-01", ["type=ADD_USER", "type=USER_MGMT", "type=ACCT_LOCK"], True,
     "local account lifecycle recorded with the acting login uid"),
    ("CM-5(1)",  "CSF PR.PS-01", ['key="identity"', 'key="sudoers"'], True,
     "audit records for writes to the files carrying access restrictions"),
    ("AU-12",    "CSF DE.CM-09", ["type=DAEMON_START"], True,
     "the audit function was operating; mapped once for the Linux host"),
    ("AU-12(3)", "CSF PR.PS-01", ["op=add_rule", "op=remove_rule"], True,
     "who changed the logging that is performed, and when"),
    ("AU-9",     "CSF PR.PS-01", ['key="audittools"'], True,
     "execution watch on the audit tool binaries, carried by a SYSCALL/PATH group"),
    ("AU-5",     "CSF DE.CM-09", ["event=audit_state"], True,
     "audit logging failure is observable: the lost counter and the enabled flag, sampled"),
    ("AC-17(1)", "CSF PR.AA-05", ["Accepted publickey", "Failed password"], True,
     "remote access with source, method and outcome"),
    ("IA-2",     "CSF PR.AA-02", ["type=USER_AUTH"], True,
     "PAM-level authentication outcome with the granting module named"),
    ("AC-7",     "CSF DE.CM-01", ["pam_faillock"], True,
     "unsuccessful logon attempts reaching the enforced limit"),
    ("AC-12",    "CSF PR.AA-05", ["Timeout, client not responding"], True,
     "automatic session termination firing on the defined condition"),
    ("SI-7",     "CSF PR.DS-06", ["event=aide_report"], True,
     "content compared against an authorized baseline; the only source here that verifies"),
    ("SI-7(1)",  "CSF PR.DS-06", ["event=aide_check"], True,
     "the scheduled check ran; the run record is the frequency evidence"),
    ("SI-6",     "CSF DE.CM-09", ["Main process exited"], True,
     "notification that a security function stopped operating"),
    ("CM-7",     "CSF PR.PS-02", ["type=SERVICE_START"], False,
     "a unit started outside the approved baseline; aggregatable"),
]

# Records a reduction pipeline may remove without costing a control above. Both
# tokens are emitted by this module on purpose: a DROPPED_BY_DESIGN token that
# never appears measures nothing.
DROPPED_BY_DESIGN = ["type=CRED_REFR", '"PRIORITY": "7"']

# (weight, kind). execve groups dominate Linux volume by a wide margin, which is
# why the auid predicate on the execve rule is the single sizing decision. AIDE,
# the audit-function state sample and the rarer control-bearing records are not
# in this table; they are scheduled through _OBLIGATIONS so a short run cannot
# omit them.
MIX = [
    (40, "exec"), (30, "journald"), (13, "secure"), (4, "login"),
    (3, "user_cmd"), (2, "watch"), (2, "service"), (1.5, "session_end"),
    (0.8, "denied"), (0.6, "sudo_refused"), (0.5, "acct_mgmt"),
    (0.3, "config_change"), (0.3, "cred_refr"), (0.2, "daemon"),
]
_W = [m[0] for m in MIX]
_K = [m[1] for m in MIX]

_BINARIES = [
    ("/usr/bin/curl", ["curl", "-fsS", "-o", "/tmp/patch.tgz", "https://repo.corp.example/patch.tgz"]),
    ("/usr/bin/systemctl", ["systemctl", "restart", "nginx"]),
    ("/usr/bin/find", ["find", "/var/www", "-name", "*.php", "-mtime", "-1"]),
    ("/usr/bin/tar", ["tar", "-xzf", "/tmp/patch.tgz", "-C", "/opt/app"]),
    ("/usr/bin/python3", ["python3", "/opt/app/bin/reindex.py", "--full"]),
    ("/usr/bin/ss", ["ss", "-tulpn"]),
    ("/usr/bin/vim", ["vim", "/etc/nginx/nginx.conf"]),
    ("/usr/bin/id", ["id"]),
    ("/usr/bin/psql", ["psql", "-h", "srv-db01", "-U", "svc_sql", "-c", "select count(*) from orders"]),
]

# (path, key, tool). The audit tool binaries carry key="audittools" from an
# execution watch, which is the AU-9 evidence; a CONFIG_CHANGE naming the same
# key is a different claim and does not substitute for it.
_WATCHED = [
    ("/etc/shadow", "identity", "vim"), ("/etc/passwd", "identity", "vim"),
    ("/etc/group", "identity", "vim"), ("/etc/sudoers.d/98-oncall", "sudoers", "visudo"),
    ("/etc/ssh/sshd_config", "sshd_config", "vim"),
    ("/etc/audit/rules.d/40-identity.rules", "auditconfig", "vim"),
    ("/usr/sbin/auditctl", "audittools", "auditctl"),
    ("/usr/sbin/augenrules", "audittools", "augenrules"),
]

# (unit, priority, identifier, comm, exe, transport, facility, message).
# systemd's own lifecycle messages carry SYSLOG_IDENTIFIER=systemd, not the
# unit's name; a journald parser keyed on the identifier reads them as the
# service's own output otherwise. Facility is part of the record and is not
# constant: sshd logs authpriv (10), systemd and units writing to stdout log
# daemon (3), and the kernel logs 0.
_UNITS = [
    ("nginx.service", 6, "nginx", "nginx", "/usr/sbin/nginx", "stdout", 3,
     "start worker process 4412"),
    ("chronyd.service", 6, "chronyd", "chronyd", "/usr/sbin/chronyd", "syslog", 3,
     "Selected source 10.20.10.1"),
    ("sshd.service", 6, "sshd", "sshd", "/usr/sbin/sshd", "syslog", 10,
     "Server listening on 0.0.0.0 port 22."),
    ("auditd.service", 3, "systemd", "systemd", "/usr/lib/systemd/systemd", "journal", 3,
     "auditd.service: Main process exited, code=killed, status=9/KILL"),
    ("aide-check.service", 6, "systemd", "systemd", "/usr/lib/systemd/systemd", "journal", 3,
     "Started AIDE file integrity check."),
    ("firewalld.service", 4, "systemd", "systemd", "/usr/lib/systemd/systemd", "journal", 3,
     "firewalld.service: Refusing to start, unit is masked."),
    ("systemd-logind.service", 6, "systemd-logind", "systemd-logind",
     "/usr/lib/systemd/systemd-logind", "journal", 4,
     "Watching system buttons on /dev/input/event0"),
    ("kernel", 4, "kernel", "kernel", "", "kernel", 0,
     "audit: backlog limit exceeded"),
]

# Priority 7 is below the collection policy's journalctl-priority = 6, so the
# live input never sends it. A journalctl capture read as a file does, which is
# what makes it the DROPPED_BY_DESIGN token the lab measures against.
_DEBUG_UNIT = ("sssd.service", 7, "sssd", "sssd", "/usr/sbin/sssd", "syslog", 3,
               "Added timed event 'ldb_kv_callback': 0x55c0f1d2a3b0")

# systemd-logind session messages, which belong to the journal. Whether they
# also reach /var/log/secure depends on the syslog bridge, so they are not
# written there.
_LOGIND_START = "8d45620b5859453cb70caf5c85ddcae8"
_LOGIND_STOP = "3354939424b4456d9802ca8333ed424a"

# Module state. Deterministic for a fixed seed, which is what the A/B arms of a
# run and the comparison between runs both depend on. Nothing here may derive
# from hash(), which is salted per process.
_SERIAL = [41000]
_SESSIONS = {}
# Queued records are held per host. A single shared queue writes a login sequence
# belonging to one host into the next host the caller happens to pick, which
# mislabels node= and breaks every join the data set is built for.
_PENDING = {}
_FIM = {}
_SESNO = {}
_SEEN = {}
_TODO = {}
_AIDE_RUN = {}

# A weighted draw leaves several control-bearing records absent from a short
# run, so the control manifest fails for a reason that has nothing to do with
# the pipeline under test. Each host discharges one of these every
# _OBLIGATION_EVERY records, in order, before the weighted draw applies.
# Ordering matters: the watches populate _FIM, which the first AIDE run reports.
_OBLIGATIONS = [
    ("daemon", {}),
    ("audit_state", {"degraded": False}),
    ("watch", {"path": "/etc/sudoers.d/98-oncall"}),
    ("watch", {"path": "/usr/sbin/auditctl"}),
    ("user_cmd", {}),
    ("denied", {}),
    ("sudo_refused", {}),
    ("acct_mgmt", {}),
    ("config_change", {}),
    ("service", {}),
    ("cred_refr", {}),
    ("session_end", {"timeout": True}),
    ("aide", {"force": "changes"}),
    ("aide", {"force": "clean"}),
]
_OBLIGATION_EVERY = 15

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _hexs(text):
    """auditd hex-encodes any field carrying whitespace or non-printable bytes."""
    return text.encode().hex().upper()


def _arg(value):
    if any(c.isspace() or c in '"\\' for c in value) or not value.isprintable():
        return _hexs(value)
    return f'"{value}"'


def _uid(user):
    """Distinct ranges per population; collapsing admins onto 1000 would make two
    different people share an auid and defeat every join in the data set."""
    if user in environment.USERS:
        return 1000 + environment.USERS.index(user)
    if user in environment.ADMINS:
        return 2000 + environment.ADMINS.index(user)
    return 1999


def _aid(when, serial):
    return f"audit({when.timestamp():.3f}:{serial})"


def _node(host, line):
    """auditd.conf name_format = hostname prefixes every record with node=.

    The prerequisite exists so the received copy carries "where the event
    occurred"; it also means a line breaker anchored on ^type= matches mid-line
    and splits the record, which is why the breaker allows for the prefix.
    """
    return f"node={host} {line}"


def _next_serial():
    _SERIAL[0] += 1
    return _SERIAL[0]


def _parse(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def _syslog_ts(when):
    """RFC3164 month names are fixed, not locale-dependent; strftime('%b') under
    a non-English LC_TIME writes a month Splunk's syslog parser cannot read."""
    return f"{_MONTHS[when.month - 1]} {when.day:2d} {when.strftime('%H:%M:%S')}"


def _digest(text, algo="sha256", width=None):
    h = hashlib.new(algo, text.encode()).hexdigest()
    return h[:width] if width else h


def _fingerprint(text):
    """OpenSSH prints key fingerprints as unpadded base64 of the SHA256 digest."""
    return base64.b64encode(hashlib.sha256(text.encode()).digest()).decode().rstrip("=")


def _selinux(kind="unconfined"):
    if kind == "system":
        return "system_u:system_r:auditd_t:s0"
    return "unconfined_u:unconfined_r:unconfined_t:s0-s0:c0.c1023"


def _boot_id(host, when):
    """One boot id per host per modeled day, so a data set spanning a reboot does
    not claim every record came from the same boot."""
    return _digest(f"{host}:boot:{when.strftime('%Y-%m-%d')}", "md5")


def _session(rng, host):
    """A session that a type=LOGIN record and a /var/log/secure line also describe.

    emit() guarantees the pool is non-empty by queueing a login first; a record
    attributed to an auid no login ever bound joins to nothing, which is the
    defect this whole data set exists to avoid.
    """
    return rng.choice(_SESSIONS[host])


def _open_session(rng, host, when):
    # Service accounts do not hold interactive pty sessions; giving svc_sql a
    # pts and a sudo history invents a person who does not exist.
    people = [u for u in environment.USERS if not u.startswith("svc_")] + environment.ADMINS
    user = rng.choice(people)
    # ses is a monotonic per-host counter in the kernel. Drawing it at random
    # lets two users on one host share a session id, and every record keyed on
    # ses then attributes to whichever of them the join reaches first.
    _SESNO[host] = _SESNO.get(host, 40) + 1
    n = rng.randrange(0, 4)
    ses = {
        "user": user,
        "auid": _uid(user),
        "ses": _SESNO[host],
        "src": environment.ip_for(rng.choice(environment.WORKSTATIONS)),
        "sport": rng.randrange(32768, 60999),
        "pid": rng.randrange(2000, 59000),
        # The kernel's tty name has no slash; sudo and the auditd USER_* records
        # print the device path, which does. A parser joining them has to know.
        "tty": f"pts{n}",
        "tty_dev": f"pts/{n}",
        "opened": when,
    }
    live = _SESSIONS.setdefault(host, [])
    live.append(ses)
    # Bounded so a long run does not accumulate sessions that never close.
    if len(live) > 6:
        live.pop(0)
    return ses


def _enrich(ses, syscall="execve", uid_name=None):
    """log_format = ENRICHED appends resolved names after an ASCII 0x1D separator.

    The separator is real, and a parser that assumes the record ends at key= takes
    the resolved names as part of the key value. AUID resolves the login uid and
    UID the effective one, which differ on anything run through sudo.
    """
    auid = ses["user"]
    uid = uid_name or auid
    return (f"\x1dARCH=x86_64 SYSCALL={syscall} AUID=\"{auid}\" UID=\"{uid}\" GID=\"{uid}\" "
            f"EUID=\"{uid}\" SUID=\"{uid}\" FSUID=\"{uid}\" EGID=\"{uid}\" SGID=\"{uid}\" "
            f"FSGID=\"{uid}\"")


def _exec_group(rng, host, when):
    ses = _session(rng, host)
    exe, argv = rng.choice(_BINARIES)
    aid = _aid(when, _next_serial())
    uid = ses["auid"]
    lines = [
        f"type=SYSCALL msg={aid}: arch=c000003e syscall=59 success=yes exit=0 "
        f"a0={rng.randrange(0x550000000000, 0x560000000000):x} "
        f"a1={rng.randrange(0x550000000000, 0x560000000000):x} "
        f"a2={rng.randrange(0x550000000000, 0x560000000000):x} a3=8 items=2 "
        f"ppid={ses['pid']} pid={rng.randrange(2000, 59000)} auid={ses['auid']} uid={uid} "
        f"gid={uid} euid={uid} suid={uid} fsuid={uid} egid={uid} sgid={uid} fsgid={uid} "
        f"tty={ses['tty']} ses={ses['ses']} comm=\"{os.path.basename(exe)}\" exe=\"{exe}\" "
        f"subj={_selinux()} key=\"exec\"{_enrich(ses)}",
        f"type=EXECVE msg={aid}: argc={len(argv)} " +
        " ".join(f"a{i}={_arg(a)}" for i, a in enumerate(argv)),
        f"type=CWD msg={aid}: cwd=\"/home/{ses['user']}\"",
        f"type=PATH msg={aid}: item=0 name=\"{exe}\" inode={rng.randrange(1000000, 9999999)} "
        f"dev=fd:00 mode=0100755 ouid=0 ogid=0 rdev=00:00 obj=system_u:object_r:bin_t:s0 "
        f"nametype=NORMAL cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0",
        f"type=PATH msg={aid}: item=1 name=\"/lib64/ld-linux-x86-64.so.2\" "
        f"inode={rng.randrange(1000000, 9999999)} dev=fd:00 mode=0100755 ouid=0 ogid=0 rdev=00:00 "
        f"obj=system_u:object_r:ld_so_t:s0 nametype=NORMAL cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 "
        f"cap_frootid=0",
        f"type=PROCTITLE msg={aid}: proctitle=" +
        (_hexs("\x00".join(argv)) if len(argv) > 1 else f'"{argv[0]}"'),
    ]
    return "\n".join(lines), {"kind": "exec", "audit_id": aid, "user": ses["user"],
                              "auid": ses["auid"], "ses": ses["ses"], "src_ip": ses["src"],
                              "exe": exe}


def _watch_group(rng, host, when, path=None):
    """A write to a watched path, or an execution of a watched binary.

    The written file is remembered so the next AIDE run reports the same path,
    which is the pairing the lab has to demonstrate.
    """
    ses = _session(rng, host)
    if path:
        entry = next((w for w in _WATCHED if w[0] == path), None) or rng.choice(_WATCHED)
    else:
        entry = rng.choice(_WATCHED)
    path, key, tool = entry
    aid = _aid(when, _next_serial())
    parent = os.path.dirname(path) or "/etc"
    if key == "audittools":
        # An execution watch on a binary, not a write to a file: the record is a
        # SYSCALL/PATH pair naming the tool that was run.
        lines = [
            f"type=SYSCALL msg={aid}: arch=c000003e syscall=59 success=yes exit=0 "
            f"a0={rng.randrange(0x550000000000, 0x560000000000):x} a1=0 a2=0 a3=8 items=1 "
            f"ppid={ses['pid']} pid={rng.randrange(2000, 59000)} auid={ses['auid']} uid=0 gid=0 "
            f"euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty={ses['tty']} ses={ses['ses']} "
            f"comm=\"{tool}\" exe=\"{path}\" subj={_selinux()} "
            f"key=\"{key}\"{_enrich(ses, 'execve', 'root')}",
            f"type=EXECVE msg={aid}: argc=2 a0=\"{tool}\" a1=\"-l\"",
            f"type=CWD msg={aid}: cwd=\"/root\"",
            f"type=PATH msg={aid}: item=0 name=\"{path}\" inode={rng.randrange(100000, 999999)} "
            f"dev=fd:00 mode=0100750 ouid=0 ogid=0 rdev=00:00 "
            f"obj=system_u:object_r:auditctl_exec_t:s0 nametype=NORMAL cap_fp=0 cap_fi=0 "
            f"cap_fe=0 cap_fver=0 cap_frootid=0",
            f"type=PROCTITLE msg={aid}: proctitle={_hexs(chr(0).join([tool, '-l']))}",
        ]
        return "\n".join(lines), {"kind": "watch", "audit_id": aid, "user": ses["user"],
                                  "auid": ses["auid"], "ses": ses["ses"], "file_path": path,
                                  "audit_key": key}
    pending = _FIM.setdefault(host, [])
    if path not in pending:
        pending.append(path)
    del pending[:-6]
    lines = [
        f"type=SYSCALL msg={aid}: arch=c000003e syscall=257 success=yes exit=3 a0=ffffff9c "
        f"a1={rng.randrange(0x550000000000, 0x560000000000):x} a2=241 a3=1b6 items=2 "
        f"ppid={ses['pid']} pid={rng.randrange(2000, 59000)} auid={ses['auid']} uid=0 gid=0 "
        f"euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty={ses['tty']} ses={ses['ses']} "
        f"comm=\"{tool}\" exe=\"/usr/bin/{tool}\" subj={_selinux()} "
        f"key=\"{key}\"{_enrich(ses, 'openat', 'root')}",
        f"type=CWD msg={aid}: cwd=\"/root\"",
        f"type=PATH msg={aid}: item=0 name=\"{parent}/\" inode={rng.randrange(100000, 999999)} "
        f"dev=fd:00 mode=040755 ouid=0 ogid=0 rdev=00:00 obj=system_u:object_r:etc_t:s0 "
        f"nametype=PARENT cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0",
        f"type=PATH msg={aid}: item=1 name=\"{path}\" inode={rng.randrange(100000, 999999)} "
        f"dev=fd:00 mode=0100640 ouid=0 ogid=0 rdev=00:00 obj=system_u:object_r:etc_t:s0 "
        f"nametype=CREATE cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0",
        f"type=PROCTITLE msg={aid}: proctitle={_hexs(chr(0).join([tool, path]))}",
    ]
    return "\n".join(lines), {"kind": "watch", "audit_id": aid, "user": ses["user"],
                              "auid": ses["auid"], "ses": ses["ses"], "file_path": path,
                              "audit_key": key}


def _denied_group(rng, host, when):
    ses = _session(rng, host)
    aid = _aid(when, _next_serial())
    uid = ses["auid"]
    path = rng.choice(["/etc/shadow", "/root/.ssh/id_ed25519", "/var/log/audit/audit.log"])
    lines = [
        f"type=SYSCALL msg={aid}: arch=c000003e syscall=257 success=no exit=-13 a0=ffffff9c "
        f"a1={rng.randrange(0x550000000000, 0x560000000000):x} a2=0 a3=0 items=1 "
        f"ppid={ses['pid']} pid={rng.randrange(2000, 59000)} auid={ses['auid']} uid={uid} gid={uid} "
        f"euid={uid} suid={uid} fsuid={uid} egid={uid} sgid={uid} fsgid={uid} tty={ses['tty']} "
        f"ses={ses['ses']} comm=\"cat\" exe=\"/usr/bin/cat\" subj={_selinux()} "
        f"key=\"access_denied\"{_enrich(ses, 'openat')}",
        f"type=CWD msg={aid}: cwd=\"/home/{ses['user']}\"",
        f"type=PATH msg={aid}: item=0 name=\"{path}\" inode={rng.randrange(100000, 999999)} "
        f"dev=fd:00 mode=0100000 ouid=0 ogid=0 rdev=00:00 obj=system_u:object_r:shadow_t:s0 "
        f"nametype=NORMAL cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0",
        f"type=PROCTITLE msg={aid}: proctitle={_hexs(chr(0).join(['cat', path]))}",
    ]
    return "\n".join(lines), {"kind": "denied", "audit_id": aid, "user": ses["user"],
                              "auid": ses["auid"], "ses": ses["ses"], "file_path": path}


def _user_cmd(rng, host, when):
    ses = _session(rng, host)
    cmd = rng.choice(["/usr/bin/systemctl restart nginx", "/usr/bin/dnf -y update openssl",
                      "/usr/sbin/aide --check", "/bin/bash", "/usr/bin/tail -f /var/log/messages"])
    aid = _aid(when, _next_serial())
    raw = (f"type=USER_CMD msg={aid}: pid={rng.randrange(2000, 59000)} uid={ses['auid']} "
           f"auid={ses['auid']} ses={ses['ses']} subj={_selinux()} "
           f"msg='cwd=\"/home/{ses['user']}\" cmd={_hexs(cmd)} exe=\"/usr/bin/sudo\" "
           f"terminal={ses['tty_dev']} res=success'"
           f"\x1dUID=\"{ses['user']}\" AUID=\"{ses['user']}\"")
    return raw, {"kind": "user_cmd", "audit_id": aid, "user": ses["user"],
                 "auid": ses["auid"], "ses": ses["ses"], "command": cmd}


def _cred_refr(rng, host, when):
    """A credential refresh, which carries no claim any control rests on.

    It is emitted so DROPPED_BY_DESIGN names a record that exists; a token the
    data set never produces measures nothing.
    """
    ses = _session(rng, host)
    aid = _aid(when, _next_serial())
    raw = (f"type=CRED_REFR msg={aid}: pid={rng.randrange(2000, 59000)} uid=0 "
           f"auid={ses['auid']} ses={ses['ses']} subj={_selinux()} "
           f"msg='op=PAM:setcred grantors=pam_env,pam_unix acct=\"root\" exe=\"/usr/bin/sudo\" "
           f"hostname=? addr=? terminal={ses['tty_dev']} res=success'")
    return raw, {"kind": "cred_refr", "audit_id": aid, "user": ses["user"],
                 "auid": ses["auid"], "ses": ses["ses"]}


def _queue_login(rng, host, when):
    """One interactive login is five auditd events, two secure lines and one
    journal record.

    They are queued rather than returned together because each carries its own
    audit id, and an emitter that fused them would hide exactly the reassembly
    defect this family is here to test.
    """
    ses = _open_session(rng, host, when)
    user, addr, port = ses["user"], ses["src"], ses["sport"]
    pid = ses["pid"]
    unset = "4294967295"
    common = f"pid={pid} uid=0 auid={unset} ses={unset} subj={_selinux('system')}"
    items = [
        ("linux:audit",
         f"type=USER_AUTH msg={_aid(when, _next_serial())}: {common} "
         f"msg='op=PAM:authentication grantors=pam_unix acct=\"{user}\" exe=\"/usr/sbin/sshd\" "
         f"hostname={addr} addr={addr} terminal=ssh res=success'"),
        ("linux:audit",
         f"type=USER_ACCT msg={_aid(when, _next_serial())}: {common} "
         f"msg='op=PAM:accounting grantors=pam_unix,pam_localuser acct=\"{user}\" "
         f"exe=\"/usr/sbin/sshd\" hostname={addr} addr={addr} terminal=ssh res=success'"),
        ("linux:audit",
         f"type=CRED_ACQ msg={_aid(when, _next_serial())}: {common} "
         f"msg='op=PAM:setcred grantors=pam_unix acct=\"{user}\" exe=\"/usr/sbin/sshd\" "
         f"hostname={addr} addr={addr} terminal=ssh res=success'"),
        ("linux:audit",
         f"type=LOGIN msg={_aid(when, _next_serial())}: pid={pid} uid=0 subj={_selinux('system')} "
         f"old-auid={unset} auid={ses['auid']} tty=(none) old-ses={unset} ses={ses['ses']} res=1"),
        ("linux:audit",
         f"type=USER_START msg={_aid(when, _next_serial())}: pid={pid} uid=0 auid={ses['auid']} "
         f"ses={ses['ses']} subj={_selinux('system')} msg='op=PAM:session_open "
         f"grantors=pam_selinux,pam_loginuid,pam_unix acct=\"{user}\" exe=\"/usr/sbin/sshd\" "
         f"hostname={addr} addr={addr} terminal=ssh res=success'"),
        ("linux_secure",
         f"{_syslog_ts(when)} {host} sshd[{pid}]: Accepted publickey for {user} from {addr} "
         f"port {port} ssh2: ED25519 SHA256:{_fingerprint(user + host)}"),
        ("linux_secure",
         f"{_syslog_ts(when)} {host} sshd[{pid}]: pam_unix(sshd:session): session opened for "
         f"user {user}(uid={ses['auid']}) by (uid=0)"),
        ("linux:journald",
         _logind_record(host, when, ses, _LOGIND_START,
                        f"New session {ses['ses']} of user {user}.")),
    ]
    q = _PENDING.setdefault(host, [])
    for stype, raw in items:
        q.append((stype, raw, {"kind": "login", "user": user, "auid": ses["auid"],
                               "ses": ses["ses"], "src_ip": addr}))


def _logind_record(host, when, ses, message_id, message):
    """systemd-logind writes the session lifecycle to the journal, under its own
    identifier, comm and unit - not sshd's."""
    record = {
        "__REALTIME_TIMESTAMP": str(int(when.timestamp() * 1_000_000)),
        "PRIORITY": "6",
        "SYSLOG_FACILITY": "4",
        "SYSLOG_IDENTIFIER": "systemd-logind",
        "MESSAGE_ID": message_id,
        "MESSAGE": message,
        "_TRANSPORT": "journal",
        "_HOSTNAME": host,
        "_BOOT_ID": _boot_id(host, when),
        "_MACHINE_ID": _digest(host + "machine", "md5"),
        "_SYSTEMD_UNIT": "systemd-logind.service",
        "_PID": "906",
        "_UID": "0",
        "_GID": "0",
        "_COMM": "systemd-logind",
        "_EXE": "/usr/lib/systemd/systemd-logind",
        "_CMDLINE": "/usr/lib/systemd/systemd-logind",
        "_AUDIT_SESSION": str(ses["ses"]),
        "_AUDIT_LOGINUID": str(ses["auid"]),
    }
    return json.dumps(record)


def _queue_session_end(rng, host, when, timeout=None):
    live = _SESSIONS.get(host) or []
    if not live:
        return _queue_login(rng, host, when)
    ses = live.pop(0)
    user, pid = ses["user"], ses["pid"]
    if timeout is None:
        timeout = rng.random() < 0.35
    items = [
        ("linux:audit",
         f"type=USER_END msg={_aid(when, _next_serial())}: pid={pid} uid=0 auid={ses['auid']} "
         f"ses={ses['ses']} subj={_selinux('system')} msg='op=PAM:session_close "
         f"grantors=pam_selinux,pam_loginuid,pam_unix acct=\"{user}\" exe=\"/usr/sbin/sshd\" "
         f"hostname={ses['src']} addr={ses['src']} terminal=ssh res=success'"),
        ("linux_secure",
         f"{_syslog_ts(when)} {host} sshd[{pid}]: Timeout, client not responding from user "
         f"{user} {ses['src']} port {ses['sport']}" if timeout else
         f"{_syslog_ts(when)} {host} sshd[{pid}]: Received disconnect from {ses['src']} "
         f"port {ses['sport']}:11: disconnected by user"),
        ("linux:journald",
         _logind_record(host, when, ses, _LOGIND_STOP, f"Removed session {ses['ses']}.")),
    ]
    q = _PENDING.setdefault(host, [])
    for stype, raw in items:
        q.append((stype, raw, {"kind": "session_end", "user": user,
                               "auid": ses["auid"], "ses": ses["ses"]}))


def _secure_line(rng, host, when):
    user = rng.choice(environment.USERS)
    pid = rng.randrange(2000, 59000)
    # The environment is air-gapped, so a successful authentication never comes
    # from outside. Only pre-authentication noise carries an external address,
    # and only to exercise a parser that has to handle one.
    internal = environment.ip_for(rng.choice(environment.WORKSTATIONS))
    r = rng.random()
    if r < 0.34:
        addr = internal if rng.random() < 0.85 else rng.choice(environment.EXTERNAL_HOSTS)
        raw = (f"{_syslog_ts(when)} {host} sshd[{pid}]: Failed password for "
               f"{'invalid user ' if rng.random() < 0.4 else ''}{user} from {addr} "
               f"port {rng.randrange(32768, 60999)} ssh2")
    elif r < 0.46:
        raw = (f"{_syslog_ts(when)} {host} sshd[{pid}]: Connection closed by authenticating user "
               f"root {internal} port {rng.randrange(32768, 60999)} [preauth]")
        addr = internal
    elif r < 0.56:
        raw = (f"{_syslog_ts(when)} {host} sshd[{pid}]: error: maximum authentication attempts "
               f"exceeded for root from {internal} port {rng.randrange(32768, 60999)} ssh2 [preauth]")
        addr = internal
    elif r < 0.64:
        raw = (f"{_syslog_ts(when)} {host} sshd[{pid}]: pam_faillock(sshd:auth): Consecutive "
               f"login failures for user {user} account temporarily locked")
        addr = internal
    elif r < 0.80:
        ses = _session(rng, host)
        raw = (f"{_syslog_ts(when)} {host} sudo[{pid}]: {ses['user']} : TTY={ses['tty_dev']} ; "
               f"PWD=/home/{ses['user']} ; USER=root ; COMMAND=/usr/bin/systemctl restart nginx")
        addr = ses["src"]
        user = ses["user"]
    elif r < 0.90:
        raw = (f"{_syslog_ts(when)} {host} su[{pid}]: pam_unix(su-l:session): session opened "
               f"for user root by {user}(uid={_uid(user)})")
        addr = internal
    else:
        raw = (f"{_syslog_ts(when)} {host} sshd[{pid}]: Accepted password for {user} from "
               f"{internal} port {rng.randrange(32768, 60999)} ssh2")
        addr = internal
    return raw, {"kind": "secure", "user": user, "src_ip": addr}


def _sudo_refused(rng, host, when):
    ses = _session(rng, host)
    raw = (f"{_syslog_ts(when)} {host} sudo[{rng.randrange(2000, 59000)}]: {ses['user']} : "
           f"user NOT in sudoers ; TTY={ses['tty_dev']} ; PWD=/home/{ses['user']} ; USER=root ; "
           f"COMMAND=/bin/su")
    return raw, {"kind": "sudo_refused", "user": ses["user"], "auid": ses["auid"],
                 "ses": ses["ses"]}


def _journald_line(rng, host, when):
    if rng.random() < 0.04:
        unit, prio, ident, comm, exe, transport, facility, message = _DEBUG_UNIT
    else:
        unit, prio, ident, comm, exe, transport, facility, message = rng.choice(_UNITS)
    record = {
        "__REALTIME_TIMESTAMP": str(int(when.timestamp() * 1_000_000)),
        "PRIORITY": str(prio),
        "SYSLOG_FACILITY": str(facility),
        "SYSLOG_IDENTIFIER": ident,
        "MESSAGE": message,
        "_TRANSPORT": transport,
        "_HOSTNAME": host,
        "_BOOT_ID": _boot_id(host, when),
        "_MACHINE_ID": _digest(host + "machine", "md5"),
    }
    if unit != "kernel":
        record.update({
            "_SYSTEMD_UNIT": unit,
            "_PID": str(rng.randrange(800, 59000)),
            "_UID": "0",
            "_GID": "0",
            "_COMM": comm[:15],
            "_EXE": exe,
            "_CMDLINE": exe,
        })
    # A system unit has no login session, so _AUDIT_SESSION is absent rather than
    # set to a user's - journald omits the field and an invented one joins to the
    # wrong actor.
    return json.dumps(record), {"kind": "journald", "unit": unit}


def _service_start(rng, host, when):
    unit = rng.choice([u[0] for u in _UNITS if u[0] != "kernel"])
    raw = (f"type=SERVICE_START msg={_aid(when, _next_serial())}: pid=1 uid=0 auid=4294967295 "
           f"ses=4294967295 subj=system_u:system_r:init_t:s0 msg='unit={unit.split('.')[0]} "
           f"comm=\"systemd\" exe=\"/usr/lib/systemd/systemd\" hostname=? addr=? terminal=? "
           f"res=success'")
    return raw, {"kind": "service", "unit": unit}


def _acct_mgmt(rng, host, when):
    ses = _session(rng, host)
    target = f"svc-{rng.choice(['backup', 'deploy', 'scan', 'oncall'])}"
    pid = rng.randrange(2000, 59000)
    head = f"pid={pid} uid=0 auid={ses['auid']} ses={ses['ses']} subj={_selinux()}"
    term = ses["tty_dev"]
    r = rng.random()
    if r < 0.35:
        raw = (f"type=ADD_USER msg={_aid(when, _next_serial())}: {head} msg='op=adding-user "
               f"id={rng.randrange(1010, 1099)} exe=\"/usr/sbin/useradd\" hostname={host} "
               f"addr=? terminal={term} res=success'")
    elif r < 0.60:
        raw = (f"type=USER_MGMT msg={_aid(when, _next_serial())}: {head} "
               f"msg='op=adding-user-to-group grp=\"wheel\" acct=\"{target}\" "
               f"exe=\"/usr/sbin/usermod\" hostname={host} addr=? terminal={term} "
               f"res=success'")
    elif r < 0.80:
        raw = (f"type=ACCT_LOCK msg={_aid(when, _next_serial())}: {head} msg='op=lock-account "
               f"acct=\"{target}\" exe=\"/usr/sbin/usermod\" hostname={host} addr=? "
               f"terminal={term} res=success'")
    else:
        raw = (f"type=USER_CHAUTHTOK msg={_aid(when, _next_serial())}: {head} "
               f"msg='op=change-password id={rng.randrange(1010, 1099)} acct=\"{target}\" "
               f"exe=\"/usr/bin/passwd\" hostname={host} addr=? terminal={term} "
               f"res=success'")
    return raw, {"kind": "acct_mgmt", "user": ses["user"], "auid": ses["auid"],
                 "target_user": target}


def _config_change(rng, host, when):
    ses = _session(rng, host)
    op, key = rng.choice([("add_rule", "identity"), ("remove_rule", "exec"),
                          ("add_rule", "audittools"), ("remove_rule", "access_denied")])
    raw = (f"type=CONFIG_CHANGE msg={_aid(when, _next_serial())}: auid={ses['auid']} "
           f"ses={ses['ses']} subj={_selinux()} op={op} key=\"{key}\" list=4 res=1"
           f"\x1dAUID=\"{ses['user']}\"")
    return raw, {"kind": "config_change", "user": ses["user"], "auid": ses["auid"],
                 "rule_key": key}


def _daemon(rng, host, when):
    if rng.random() < 0.7:
        raw = (f"type=DAEMON_START msg={_aid(when, _next_serial())}: op=start ver=3.1.2 "
               f"format=enriched kernel=5.14.0-503.el9.x86_64 auid=4294967295 pid="
               f"{rng.randrange(900, 1500)} uid=0 ses=4294967295 "
               f"subj=system_u:system_r:auditd_t:s0 res=successful")
    else:
        raw = (f"type=DAEMON_ROTATE msg={_aid(when, _next_serial())}: op=rotate-logs "
               f"auid=4294967295 pid={rng.randrange(900, 1500)} uid=0 ses=4294967295 "
               f"subj=system_u:system_r:auditd_t:s0 res=success")
    return raw, {"kind": "daemon"}


def _audit_state(rng, host, when, degraded=False):
    """The rule set and the kernel's audit counters, sampled.

    This is configuration state, not an event stream: every sample restates the
    same facts, so it is read with latest() by host and counted never. It is
    emitted as key=value so auto-kv reaches lost, enabled and rules - the shape
    `auditctl -s` prints is space-separated pairs, which auto-kv does not parse.
    """
    if degraded:
        enabled, lost, rules, wait = 1, rng.randrange(40, 9000), 3, 0
    else:
        enabled, lost, rules, wait = 2, 0, 71, 0
    raw = (f"{when.strftime('%Y-%m-%dT%H:%M:%S%z')} host={host} event=audit_state "
           f"enabled={enabled} failure=1 pid={rng.randrange(900, 1500)} rate_limit=0 "
           f"backlog_limit=8192 lost={lost} backlog={rng.randrange(0, 40)} "
           f"backlog_wait_time=60000 backlog_wait_time_actual={wait} "
           f"loginuid_immutable=1 rules={rules}")
    return raw, {"kind": "audit_state", "enabled": enabled, "lost": lost, "rules": rules}


def _queue_aide(rng, host, when, force=None):
    """An AIDE run: the report, the status line the collector keys on, and - only
    when the exclusion set changes - the configuration record.

    The status line is separate because the report can be megabytes and is
    truncated by the wrapper; the run record must survive that truncation or a
    check that did not run is indistinguishable from a check that found nothing.
    """
    run_no = _AIDE_RUN.get(host, 0) + 1
    _AIDE_RUN[host] = run_no
    if force == "changes":
        changed = _FIM.pop(host, [])
    elif force == "clean":
        changed = []
    else:
        # Most real runs are clean, and the lab has to prove the clean shape
        # parses: a collector that only ever sees a findings report reads a
        # broken check as a working one.
        changed = [] if rng.random() < 0.55 else _FIM.pop(host, [])
    # Derived, not hash()-derived: hash() is salted per process, so a run_id
    # built from it differs between two runs of the same seed and joins to
    # nothing across the A and B arms.
    run_id = _digest(f"{host}:aide:{run_no}", "sha256", 12)
    duration = rng.randrange(90, 400)
    started = when - timedelta(seconds=duration)
    entries = rng.randrange(112000, 126000)
    added = len([p for p in changed if "sudoers.d" in p])
    modified = [p for p in changed if "sudoers.d" not in p]
    rc = (1 if added else 0) | (4 if modified else 0)
    result = "clean" if rc == 0 else "changes"
    db_hash = _digest(host + "aidedb", "sha512")

    head = (f"{started.strftime('%Y-%m-%dT%H:%M:%S%z')} host={host} event=aide_report "
            f"run_id={run_id} rc={rc} result={result} added={added} removed=0 "
            f"changed={len(modified)} entries={entries} detail_truncated=false")
    body = [f"Start timestamp: {started.strftime('%Y-%m-%d %H:%M:%S %z')} (AIDE 0.16)"]
    if rc == 0:
        body += ["AIDE found NO differences between database and filesystem. Looks okay!!", "",
                 "Summary:", f"  Total number of entries:\t{entries}",
                 "  Added entries:\t\t0", "  Removed entries:\t\t0", "  Changed entries:\t\t0"]
    else:
        body += ["AIDE found differences between database and filesystem!!", "",
                 "Summary:", f"  Total number of entries:\t{entries}",
                 f"  Added entries:\t\t{added}", "  Removed entries:\t\t0",
                 f"  Changed entries:\t\t{len(modified)}", ""]
        if added:
            body += ["---------------------------------------------------",
                     "Added entries:",
                     "---------------------------------------------------", ""]
            body += [f"f++++++++++++++++: {p}" for p in changed if "sudoers.d" in p]
            body += [""]
        if modified:
            body += ["---------------------------------------------------",
                     "Changed entries:",
                     "---------------------------------------------------", ""]
            body += [f"f   ...    .C... : {p}" for p in modified]
            body += ["", "---------------------------------------------------",
                     "Detailed information about changes:",
                     "---------------------------------------------------", ""]
            for p in modified:
                body += [f"File: {p}",
                         f"  SHA512   : {_digest(p, 'sha512', 44)}",
                         f"             {_digest(p + 'new', 'sha512', 44)}",
                         f"  Size     : {rng.randrange(400, 9000)}"
                         f"                            | {rng.randrange(400, 9000)}",
                         f"  Mtime    : {(started - timedelta(days=44)).strftime('%Y-%m-%d %H:%M:%S %z')}"
                         f"   | {(started - timedelta(minutes=31)).strftime('%Y-%m-%d %H:%M:%S %z')}",
                         ""]
    body += [f"End timestamp: {when.strftime('%Y-%m-%d %H:%M:%S %z')} (run time: "
             f"{duration // 60}m {duration % 60}s)"]
    tail = (f"{when.strftime('%Y-%m-%dT%H:%M:%S%z')} host={host} event=aide_report_end "
            f"run_id={run_id} duration_s={duration}")
    q = _PENDING.setdefault(host, [])
    q.append(("aide:report", "\n".join([head] + body + [tail]),
              {"kind": "aide_report", "run_id": run_id, "rc": rc,
               "changed_paths": list(changed)}))

    status = (f"{when.strftime('%Y-%m-%dT%H:%M:%S%z')} host={host} event=aide_check "
              f"run_id={run_id} rc={rc} result={result} added={added} removed=0 "
              f"changed={len(modified)} entries={entries} duration_s={duration} "
              f"config=/etc/aide.conf config_sha256={_digest(host + 'cfg')} "
              f"db=/var/lib/aide/aide.db.gz db_sha512={db_hash} "
              f"db_mtime={(started - timedelta(days=12)).strftime('%Y-%m-%dT%H:%M:%S%z')} "
              f"schedule=aide-check.timer")
    q.append(("aide:status", status, {"kind": "aide_status", "run_id": run_id, "rc": rc}))

    # The exclusion set is state. Emitting it every run multiplies one fact by
    # the number of checks, so it is emitted only when it changes - here, the
    # first run on a host.
    if run_no == 1:
        cfg = (f"{when.strftime('%Y-%m-%dT%H:%M:%S%z')} host={host} event=aide_config "
               f"run_id={run_id} config_sha256={_digest(host + 'cfg')} "
               f"excluded=\"/var/log,/var/tmp,/var/spool,/tmp,/home,/proc,/sys,/dev,/run\"")
        q.append(("aide:status", cfg, {"kind": "aide_config", "run_id": run_id}))


_BUILDERS = {
    "exec": _exec_group, "watch": _watch_group, "denied": _denied_group,
    "user_cmd": _user_cmd, "secure": _secure_line, "sudo_refused": _sudo_refused,
    "journald": _journald_line, "service": _service_start, "acct_mgmt": _acct_mgmt,
    "config_change": _config_change, "daemon": _daemon, "cred_refr": _cred_refr,
    "audit_state": _audit_state,
}
_QUEUERS = {"login": _queue_login, "session_end": _queue_session_end, "aide": _queue_aide}

_STREAM_OF = {
    "exec": "linux:audit", "watch": "linux:audit", "denied": "linux:audit",
    "user_cmd": "linux:audit", "service": "linux:audit", "acct_mgmt": "linux:audit",
    "config_change": "linux:audit", "daemon": "linux:audit", "cred_refr": "linux:audit",
    "secure": "linux_secure", "sudo_refused": "linux_secure",
    "journald": "linux:journald", "audit_state": "linux:audit_state",
}


def _obligations_for(host):
    """Per-host obligation list. One host in four also gets a degraded audit
    state sample, so the standing check has something to fire on without every
    host reading as broken."""
    todo = list(_OBLIGATIONS)
    if _digest(host)[0] in "0123":
        todo.insert(2, ("audit_state", {"degraded": True}))
    return todo


def emit(rng, host, record_id, ts):
    """One record. meta carries the per-record sourcetype, because this family
    is five sources on one host and a single module-level SOURCETYPE would put
    sshd text and JSON into the same parser."""
    # Linux host names are lower case on the wire. The driver passes
    # environment.LINUX entries as written, so normalising here is what keeps
    # node=, _HOSTNAME and the seed file path naming one machine.
    host = host.lower()
    when = _parse(ts)
    queue = _PENDING.setdefault(host, [])
    seen = _SEEN.setdefault(host, 0) + 1
    _SEEN[host] = seen
    if host not in _TODO:
        _TODO[host] = _obligations_for(host)
    if queue:
        stype, raw, meta = queue.pop(0)
    elif not _SESSIONS.get(host):
        # No session on this host yet, so the login has to come first: a SYSCALL
        # record that precedes the LOGIN binding its auid cannot be attributed.
        _queue_login(rng, host, when)
        stype, raw, meta = queue.pop(0)
    else:
        todo = _TODO[host]
        if todo and seen % _OBLIGATION_EVERY == 0:
            kind, kwargs = todo.pop(0)
        else:
            kind, kwargs = rng.choices(_K, weights=_W, k=1)[0], {}
        if kind in _QUEUERS:
            _QUEUERS[kind](rng, host, when, **kwargs)
            stype, raw, meta = queue.pop(0)
        else:
            raw, meta = _BUILDERS[kind](rng, host, when, **kwargs)
            stype = _STREAM_OF[kind]
    if stype == "linux:audit":
        raw = "\n".join(_node(host, line) for line in raw.split("\n"))
    source, index = STREAMS[stype]
    meta.update({"sourcetype": stype, "source": source, "index": index,
                 "host": host, "multiline": "\n" in raw})
    return raw, meta


def reset():
    """Clear per-run state. harness.calibrate() runs 400 emits on a throwaway RNG
    before the data set starts, and those sessions, serials and obligations would
    otherwise carry into it. The driver must call this after calibrate()."""
    _SERIAL[0] = 41000
    _SESSIONS.clear()
    _PENDING.clear()
    _FIM.clear()
    _SESNO.clear()
    _SEEN.clear()
    _TODO.clear()
    _AIDE_RUN.clear()


def main(argv=None):
    """Write one seed file per sourcetype, with real newlines inside auditd
    groups and AIDE reports. This is the path the Splunk lab uses; the Cribl
    driver escapes newlines and cannot carry this family."""
    import argparse
    import random

    ap = argparse.ArgumentParser(description="Linux host seed data for the Splunk lab")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--count", type=int, default=20000)
    ap.add_argument("--rate", type=int, default=400, help="records per second of modeled time")
    ap.add_argument("--span-seconds", type=int, default=0, dest="span",
                    help="stretch the run over this much modeled time; "
                         "default count/rate, which is seconds, not a working day")
    ap.add_argument("--seed", type=int, default=1729)
    ap.add_argument("--hosts", default=",".join(environment.LINUX))
    args = ap.parse_args(argv)

    reset()
    rng = random.Random(args.seed)
    hosts = [h.lower() for h in args.hosts.split(",") if h]
    # Below roughly 200 records per host the obligation list does not drain and
    # the control manifest has gaps that are the generator's, not the pipeline's.
    per_host = args.count / max(len(hosts), 1)
    if per_host < _OBLIGATION_EVERY * (len(_OBLIGATIONS) + 1):
        print(f"warning: {per_host:.0f} records per host is below the "
              f"{_OBLIGATION_EVERY * (len(_OBLIGATIONS) + 1)} needed to emit every "
              f"control-bearing record; raise --count", file=sys.stderr)
    os.makedirs(args.out_dir, exist_ok=True)
    names = {"linux:audit": "audit.log", "linux_secure": "secure",
             "linux:journald": "journald.json", "aide:report": "aide-check.log",
             "aide:status": "aide-status.log", "linux:audit_state": "audit-state.log"}
    files, counts = {}, {}
    for host in hosts:
        os.makedirs(os.path.join(args.out_dir, host), exist_ok=True)
        for stype, name in names.items():
            path = os.path.join(args.out_dir, host, name)
            files[(host, stype)] = open(path, "w", encoding="utf-8")
            counts[(host, stype)] = 0
    span = args.span or (args.count / max(args.rate, 1))
    base = datetime.now(timezone.utc) - timedelta(seconds=span)
    step = span / max(args.count, 1)
    try:
        for i in range(args.count):
            host = rng.choice(hosts)
            when = base + timedelta(seconds=i * step)
            ts = when.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            raw, meta = emit(rng, host, i + 1, ts)
            files[(host, meta["sourcetype"])].write(raw + "\n")
            counts[(host, meta["sourcetype"])] += 1
    finally:
        for f in files.values():
            f.close()
    for (host, stype), n in sorted(counts.items()):
        path = os.path.join(args.out_dir, host, names[stype])
        print(f"seed host={host} sourcetype={stype} events={n} "
              f"bytes={os.path.getsize(path)} path={path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
