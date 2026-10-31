"""
Trellix ePO CSV export and the configuration state extracts.

Two evidence kinds in one module because they share an origin, a schedule and a
set of correlation handles. The ePO export is three CSV files published
atomically by a producer outside Splunk; the state extracts are scheduled
command output, one record per volume, per audit subcategory or per audit rule.
Neither is an event stream, and a search that sums state snapshots across a
window reports the population multiplied by the number of collections.

emit() returns one ePO events CSV DATA ROW, which is exactly what Splunk stores
as _raw under INDEXED_EXTRACTIONS = csv, so the harness calibrates and accounts
this source on the same terms as every syslog source. The header row is a
property of the file rather than of a record, so anything that has to PARSE must
be driven through publish_csv_cycle() instead of the harness's line writer.

The Trellix module state is not a fourth feed. OASEnabled, AMCoreContentVersion
and ODSLastScanDate ride the agent_health CSV, and inventing a separate
sourcetype for them would put the same population in the index twice.

DELIBERATELY NOT REGISTERED IN sources.ALL. The driver's line writer produces
one <KEY>.log per module with no header row, which for a csv sourcetype is a
feed that parses into nothing; and a sixteenth weighted source would move the
mix the existing reduction measurement was taken against. Drive this module
through its own main().
"""

import argparse
import csv
import hashlib
import io
import json
import os
import random
from datetime import datetime, timedelta, timezone

try:
    import environment
except ImportError:  # standalone use, outside the harness driver
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import environment


KEY = "trellix_epo"
SOURCETYPE = "trellix:epo:events"
SOURCE = "epo-events.csv"
# Endpoint security detections are single digits to low hundreds per thousand
# endpoints per day on a tuned fleet; the state extracts are larger than this
# feed and are accounted separately because they are not events.
SHARE = 0.3

CONTROL_FIELD = "threat_type"

CONTROLS = [
    ("SI-3",    "CSF PR.PS-05", ["trojan", "virus", "pup"], True,
     "malicious code detected and the configured response action taken"),
    ("SI-3(8)", "CSF DE.CM-01", ["exploit"], True,
     "unauthorized command execution prevented by a named Exploit Prevention signature"),
    ("SI-16",   "CSF PR.PS-01", ["exploit"], True,
     "memory protection enforcing at the moment of the attempt"),
    ("MP-7",    "CSF PR.DS-01", ["data-loss"], True,
     "removable media use restricted by a technical control"),
    ("CM-8(3)", "CSF ID.AM-01", ["data-loss"], True,
     "automated detection of unauthorized peripheral hardware"),
    ("IR-4(1)", "CSF RS.MA-01", ["trojan", "virus", "behavior"], True,
     "automated endpoint containment, with detection-to-action elapsed time per record"),
    ("AU-3",    "CSF PR.PS-04", ["trojan", "data-loss"], True,
     "content of audit records for the ENS and DLP components"),
]

# The state extracts evidence different controls on a different field, so they
# are declared apart rather than folded into the event manifest above.
STATE_CONTROL_FIELD = "extract"
STATE_CONTROLS = [
    ("SC-28",    "CSF PR.DS-01", ["bitlocker", "luks"], True,
     "which volumes are protected at rest and which are not"),
    ("SC-28(1)", "CSF PR.DS-01", ["bitlocker", "luks"], True,
     "cipher, mode and key size in force per volume"),
    ("SC-28(3)", "CSF PR.DS-01", ["bitlocker"], True,
     "key protector type per volume - a hardware-protected key store or a recovery password alone"),
    ("SC-12",    "CSF PR.DS-01", ["bitlocker_escrow"], True,
     "recovery key material escrowed in AD DS, which is not on the host"),
    ("AU-2",     "CSF PR.PS-04", ["auditpol", "auditd"], True,
     "the audit settings actually in force per host, not per Group Policy object"),
    ("AU-12",    "CSF DE.CM-01", ["auditpol", "auditd"], True,
     "audit record generation enabled for the event types the rest of the matrix depends on"),
    ("SI-3",     "CSF PR.PS-05", ["agent_health"], True,
     "on-access scanning enabled and content currency per endpoint - the SI-3 halves no event carries"),
    ("CM-6",     "CSF PR.PS-01", ["auditpol", "auditd", "bitlocker", "luks"], True,
     "mandated configuration settings implemented on the running host"),
]

DROPPED_BY_DESIGN = []


# ---------------------------------------------------------------- environment

# NetBIOS form of the shared domain. ePO publishes os_domain in this form and
# every user string in the export is DOMAIN\sam, which is how a row joins a
# Windows 4624 for the same person.
NETBIOS = environment.DOMAIN.split(".")[0].upper()

EPO_SERVER = "EPO01"
MANAGED = environment.WORKSTATIONS + environment.SERVERS + environment.DCS

# Two systems that have never communicated. Their watermark columns are null
# forever, so a producer that filters on the watermark drops exactly the failed
# deployments the estate feeds exist to surface.
NEVER_COMMUNICATED = (environment.SERVERS[-1], environment.WORKSTATIONS[-1])
# One endpoint with no ENS at all and one with ENS installed and On-Access Scan
# off: a coverage denominator cannot tell an unprotected host from a clean one
# unless both cases are in the data.
ENS_ABSENT = (environment.WORKSTATIONS[3],)
OAS_DISABLED = (environment.WORKSTATIONS[7], environment.SERVERS[2])
# Exploit Prevention not installed. The column is null here, and a null is not
# proof the feature is off - the two cases have to be separated before any
# coverage number is published.
EXPLOIT_PREVENTION_ABSENT = (environment.WORKSTATIONS[11], environment.WORKSTATIONS[12])

AGENT_VERSION = "5.7.9.128"
ENS_PRODUCT_VERSION = "10.7.0"
ENGINE_VERSION = "6700.10107"
CONTENT_VERSION = "5.2.26080.5447"
EXPLOIT_CONTENT_VERSION = "12.8.0.242"


def _guid_for(name):
    """Stable per-host agent GUID. sha256 rather than md5 because md5 raises
    under a FIPS-enabled Python, and a GUID that moves between cycles breaks
    every correlation keyed on agent_guid."""
    h = hashlib.sha256(("epo-agent:" + name).encode()).hexdigest().upper()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _ipv4x(ip):
    """ePO stores IPV4x as offset binary - the unsigned 32-bit address minus
    2^31 - and the column is meaningless read raw."""
    a, b, c, d = (int(o) for o in ip.split("."))
    return ((a << 24) | (b << 16) | (c << 8) | d) - (1 << 31)


def _os_for(host):
    if host in environment.DCS:
        return ("Windows Server 2022", "10.0.20348", "20348", "Domain controller")
    if host in environment.SERVERS:
        return ("Windows Server 2022", "10.0.20348", "20348", "Managed server")
    return ("Windows 11 Enterprise", "10.0.22631", "22631", "Managed workstation")


def _tags_for(host):
    if host in environment.DCS:
        return "Domain Controller,Managed"
    if host in environment.SERVERS:
        return "Server,Managed"
    return "Workstation,Managed"


def _iso(when):
    return when.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _stamp(when):
    return when.strftime("%Y%m%d-%H%M%S")


# ------------------------------------------------------------- event profiles

# ThreatEventIDs 1027, 1035, 1092 and 1278 are the file-detection values this
# environment's data set carries. Every other id below is a lab placeholder:
# the authoritative per-instance vocabulary is dbo.EPOEventFilterDesc joined on
# ThreatEventID and must be read off the instance before anything keys on it.
ENS_PROFILES = [
    (30, "ENS Threat Prevention", "Signature", "trojan", "Malware", [1278],
     ["Trojan-FVCP!MSIL", "W97M/Downloader.dxu", "Generic.tfr!m"]),
    (12, "ENS Threat Prevention", "Signature", "virus", "Malware", [1027, 1035],
     ["EICAR test file", "W32/Sality.gen"]),
    (8,  "ENS Threat Prevention", "On-Demand Scan", "pup", "Malware", [1092],
     ["PUP-XDF-KL", "PUP/RemoteAdmin"]),
    (14, "ENS Threat Prevention", "Exploit Prevention", "exploit", "Malware", [1090],
     ["6013 Generic Buffer Overflow Protection",
      "6086 PowerShell Command Restriction - Suspicious",
      "6087 PowerShell Command Restriction - Encoded"]),
    (18, "ENS ATP", "Behavioral", "behavior", "Adaptive Threat Protection", [1091],
     ["ATP/Suspicious.PowerShell", "ATP/CredentialAccess", "ATP/RansomBehavior",
      "T1003.001_OS_Credential_Dumping_LSASS_Memory_0"]),
    (8,  "ENS Firewall", "Signature", "ids", "Network", [1093],
     ["Block Outbound C2 Port", "Block Inbound SMB"]),
    (6,  "ENS Web Control", "Signature", "web", "Web", [1094],
     ["Blocked Red Site", "Blocked Uncategorized Site"]),
    (4,  "Solidcore", "Signature", "integrity", "Integrity", [1095],
     ["Execution Denied", "Write Denied"]),
]

# ThreatActionTaken as ePO emits it, with the decoded verb the export writes
# beside it and the ThreatHandled result bit. would-block is the Report-mode
# case: it is a detection and not an enforcement.
ENS_ACTIONS = [
    (26, "IDS_ACTION_DELETED", "deleted", 1),
    (24, "IDS_ACTION_CLEANED", "cleaned", 1),
    (22, "IDS_ACTION_BLOCKED", "blocked", 1),
    (14, "IDS_ACTION_NONE", "none", 0),
    (10, "IDS_ACTION_WOULD_BLOCK", "would-block", 0),
]

DLP_PROFILES = [
    (34, "Removable Media", "dlp.classification.pii",
     ["PII - National ID Pattern", "PII - Personnel Record"]),
    (18, "Web Post", "dlp.classification.confidential",
     ["Confidential - Marked Document", "Confidential - Design Document"]),
    (18, "Email", "dlp.classification.financial",
     ["Financial - Account Number Pattern"]),
    (15, "Cloud Sync", "dlp.classification.source_code",
     ["Source Code - Repository Content"]),
    (15, "Network Share", "dlp.classification.confidential",
     ["Confidential - Marked Document"]),
]

DLP_ACTIONS = [
    (34, "IDS_ALERT_ACT_TAK_BLOCK", "blocked", 1),
    (28, "IDS_ALERT_ACT_TAK_NONE", "none", 0),
    (22, "IDS_ALERT_ACT_TAK_CONTINUE", "allowed", 1),
    (16, "IDS_ALERT_ACT_TAK_QUAR", "quarantined", 1),
]

DOC_NAMES = ["benefits-enrollment-2026.xlsx", "personnel-roster.csv", "design-review.docx",
             "quarterly-forecast.xlsx", "site-survey-notes.docx", "keys-backup.zip"]
EXFIL_URLS = ["https://paste.ee/upload", "https://api.telegram.org/bot/sendDocument",
              "https://cdn77-assets.b-cdn.net/put"]


def _pick(rng, table):
    """Weighted choice over a table whose first element is the weight."""
    return rng.choices(table, weights=[t[0] for t in table], k=1)[0]


EVENT_COLUMNS = (
    "record_id", "detected", "received", "event_time_local", "ingest_lag_seconds",
    "module", "product", "product_version", "engine_version", "content_version",
    "detection_method", "server_id", "event_id", "signature", "threat_type",
    "threat_category", "severity_id", "threat_handled", "action_raw", "action",
    "dest", "dest_ip", "dest_ipv6", "dest_mac", "dest_port", "dest_protocol",
    "user", "file_name", "dest_process", "src", "src_ip", "src_ipv6", "src_mac",
    "src_process", "src_user", "src_url", "reporter_host", "reporter_ip",
    "reporter_ipv6", "reporter_mac", "dest_ip_raw", "src_ip_raw", "agent_guid",
    "agent_node_name", "agent_last_comm", "agent_tags", "os_domain",
    "os_logged_user", "system_desc", "system_match",
)

SYSTEMS_COLUMNS = (
    "dest", "agent_guid", "agent_version", "managed_state", "last_properties_update",
    "snapshot_time", "hours_since_comm", "agent_tags", "sequence_errors", "node_os",
    "computer_name", "ip", "ip_raw", "ipv6", "os_type", "os_version", "os_platform",
    "os_build", "os_domain", "last_user", "system_description", "time_zone",
    "cpu_type", "total_memory", "free_disk", "is_portable", "properties_present",
)

HEALTH_COLUMNS = (
    "dest", "agent_guid", "agent_version", "managed_state", "last_comm",
    "snapshot_time", "hours_since_comm", "sequence_errors", "agent_tags",
    "ens_installed", "oas_enabled", "engine_version", "content_version",
    "content_date", "exploit_content_version", "last_ods_scan",
    "firewall_installed", "solidcore_mode",
)


def event_row(rng, record_id, when):
    """One ePO event as a dict keyed by EVENT_COLUMNS.

    Every endpoint identifier is drawn from the shared environment, so a
    detection joins the Windows logon, the DHCP lease and the ISE
    authentication for the same machine and the same person.
    """
    dest = rng.choice(MANAGED)
    sam = rng.choice(environment.USERS)
    dest_ip = environment.ip_for(dest)
    dest_mac = environment.mac_for(dest)
    is_dlp = rng.random() < 0.20

    # Agent-to-server lag. On the default 60-minute communication interval this
    # is the whole latency, and these two timestamps are what disprove a
    # near-real-time claim rather than support it.
    lag = rng.randrange(2, 90) if rng.random() < 0.75 else rng.randrange(600, 3600)
    received = when + timedelta(seconds=lag)

    row = {c: "" for c in EVENT_COLUMNS}
    row.update({
        "record_id": record_id,
        "detected": _iso(when),
        "received": _iso(received),
        "event_time_local": _iso(when),
        "ingest_lag_seconds": lag,
        "product_version": ENS_PRODUCT_VERSION,
        "engine_version": ENGINE_VERSION,
        "content_version": CONTENT_VERSION,
        "server_id": EPO_SERVER,
        "dest": dest,
        "dest_ip": dest_ip,
        "dest_mac": dest_mac,
        "user": f"{NETBIOS}\\{sam}",
        "src": dest,
        "src_ip": dest_ip,
        "reporter_host": EPO_SERVER,
        "reporter_ip": environment.ip_for(EPO_SERVER),
        "dest_ip_raw": _ipv4x(dest_ip),
        "src_ip_raw": _ipv4x(dest_ip),
        "agent_guid": _guid_for(dest),
        "agent_node_name": dest,
        "agent_last_comm": _iso(when - timedelta(minutes=rng.randrange(5, 180))),
        "agent_tags": _tags_for(dest),
        "os_domain": NETBIOS,
        "os_logged_user": sam,
        "system_desc": _os_for(dest)[3],
        "system_match": "guid",
    })

    if is_dlp:
        _, channel, classification, signatures = _pick(rng, DLP_PROFILES)
        _, action_raw, action, handled = _pick(rng, DLP_ACTIONS)
        doc = rng.choice(DOC_NAMES)
        path = {"Removable Media": f"E:\\{doc}",
                "Network Share": f"\\\\{environment.SERVERS[0]}\\share\\{doc}",
                "Email": f"C:\\Users\\{sam}\\Documents\\{doc}",
                "Cloud Sync": f"C:\\Users\\{sam}\\OneDrive\\{doc}",
                "Web Post": f"C:\\Users\\{sam}\\Downloads\\{doc}"}[channel]
        row.update({
            "module": "dlp",
            "product": "Trellix Data Loss Prevention",
            "detection_method": channel,
            "event_id": 1027 if channel == "Removable Media" else 1096,
            "signature": rng.choice(signatures),
            "threat_type": "data-loss",
            "threat_category": classification,
            "severity_id": rng.choice([1, 2, 2, 3, 3, 4]),
            "threat_handled": handled,
            "action_raw": action_raw,
            "action": action,
            "file_name": path,
            "src_process": "C:\\Windows\\explorer.exe",
            "src_user": f"{NETBIOS}\\{sam}",
            "src_url": rng.choice(EXFIL_URLS) if channel == "Web Post" else "",
        })
    else:
        _, product, method, ttype, category, event_ids, signatures = _pick(rng, ENS_PROFILES)
        _, action_raw, action, handled = _pick(rng, ENS_ACTIONS)
        row.update({
            "module": "endpoint",
            "product": product,
            "detection_method": method,
            "event_id": rng.choice(event_ids),
            "signature": rng.choice(signatures),
            "threat_type": ttype,
            "threat_category": category,
            "severity_id": rng.choice([1, 2, 2, 3, 3, 4, 5, 6]),
            "threat_handled": handled,
            "action_raw": action_raw,
            "action": action,
            "file_name": f"C:\\Users\\{sam}\\Downloads\\sample{record_id % 10000:04d}.exe",
            "dest_process": "explorer.exe",
        })
        if ttype == "ids":
            row["dest_port"] = rng.choice([445, 3389, 4444, 8443])
            row["dest_protocol"] = "TCP"
            row["src_url"] = ""
        if ttype == "web":
            row["src_url"] = rng.choice(EXFIL_URLS)

    # The unmapped and the absent action. The export preserves an unmapped
    # ThreatActionTaken as its raw key and writes an empty column when ePO
    # recorded none; both must reach the lab or the add-on's `unknown` branch
    # is never exercised.
    draw = rng.random()
    if draw < 0.015:
        row["action_raw"] = "IDS_ACTION_TAK_RESERVED_7"
        row["action"] = "IDS_ACTION_TAK_RESERVED_7"
    elif draw < 0.03:
        row["action_raw"] = ""
        row["action"] = ""
    return row


def emit(rng, host, record_id, ts):
    """One CSV data row, which is what Splunk stores as _raw for this feed.

    The header lives in the file, so this row alone does not parse; it exists so
    the harness weights and accounts this source the same way it does a syslog
    source. host is the ePO server, because Splunk's host metadata is the
    machine that forwarded the file and never the endpoint.
    """
    when = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    row = event_row(rng, record_id, when)
    raw = _csv_line([row.get(c, "") for c in EVENT_COLUMNS])
    return raw, {"module": row["module"], "threat_type": row["threat_type"],
                 "dest": row["dest"], "action": row["action"]}


def _csv_line(values):
    """csv.writer semantics without a file, so a single row quotes exactly as it
    does inside a published export."""
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(values)
    return buf.getvalue()


# ----------------------------------------------------------- estate snapshots

def systems_rows(rng, hosts, when):
    rows = []
    for host in hosts:
        never = host in NEVER_COMMUNICATED
        node_os, os_version, os_build, desc = _os_for(host)
        last_update = "" if never else _iso(when - timedelta(hours=rng.randrange(1, 26)))
        ip = environment.ip_for(host)
        rows.append({
            "dest": host,
            "agent_guid": _guid_for(host),
            "agent_version": AGENT_VERSION,
            "managed_state": 1,
            "last_properties_update": last_update,
            # snapshot_time is the only column on this feed guaranteed to have a
            # value, and the feed is timestamped on it. A null timestamp field
            # does not fail loudly: Splunk gives the row the PREVIOUS row's time.
            "snapshot_time": last_update or _iso(when),
            "hours_since_comm": "" if never else rng.randrange(1, 26),
            "agent_tags": _tags_for(host),
            "sequence_errors": 0,
            "node_os": node_os,
            "computer_name": host,
            "ip": ip,
            "ip_raw": _ipv4x(ip),
            "ipv6": "",
            "os_type": "Windows",
            "os_version": os_version,
            "os_platform": node_os,
            "os_build": os_build,
            "os_domain": NETBIOS,
            "last_user": "" if never else rng.choice(environment.USERS),
            "system_description": desc,
            "time_zone": "UTC",
            "cpu_type": "Intel(R) Xeon(R) Gold 6248R",
            "total_memory": 17179869184,
            "free_disk": rng.randrange(40, 400) * 1024 ** 3,
            "is_portable": 1 if host in environment.WORKSTATIONS and rng.random() < 0.4 else 0,
            "properties_present": 0 if never else 1,
        })
    return rows


def agent_health_rows(rng, hosts, when):
    """The Trellix module state feed: OASEnabled, content currency and last
    on-demand scan per endpoint, which is the SI-3 evidence no event carries."""
    rows = []
    for host in hosts:
        never = host in NEVER_COMMUNICATED
        ens = 0 if host in ENS_ABSENT else 1
        oas = 0 if (not ens or host in OAS_DISABLED) else 1
        last_comm = "" if never else _iso(when - timedelta(hours=rng.randrange(0, 30)))
        rows.append({
            "dest": host,
            "agent_guid": _guid_for(host),
            "agent_version": AGENT_VERSION,
            "managed_state": 1,
            "last_comm": last_comm,
            "snapshot_time": last_comm or _iso(when),
            "hours_since_comm": "" if never else rng.randrange(0, 30),
            "sequence_errors": 0 if rng.random() > 0.05 else rng.randrange(1, 4),
            "agent_tags": _tags_for(host),
            "ens_installed": ens,
            "oas_enabled": oas,
            "engine_version": ENGINE_VERSION if ens else "",
            "content_version": CONTENT_VERSION if ens else "",
            # A small tail of endpoints carries content that is weeks old, which
            # is the SI-3 currency finding the coverage number exists to surface.
            "content_date": "" if not ens else _iso(
                when - timedelta(days=rng.choice([0, 0, 0, 1, 1, 2, 9, 23]))),
            "exploit_content_version": "" if (not ens or host in EXPLOIT_PREVENTION_ABSENT)
                                       else EXPLOIT_CONTENT_VERSION,
            "last_ods_scan": "" if not ens else _iso(
                when - timedelta(days=rng.choice([1, 2, 5, 7, 7, 14, 61]))),
            "firewall_installed": ens,
            "solidcore_mode": "" if host in environment.WORKSTATIONS else "Enabled",
        })
    return rows


def _changed_since(rng, when, fraction):
    """A watermarked cycle carries only the systems whose agent updated. The
    never-communicated rows are carried every cycle regardless, because any
    comparison against a null watermark excludes them for the life of the
    deployment."""
    pool = [h for h in MANAGED if h not in NEVER_COMMUNICATED]
    n = max(1, int(len(pool) * fraction))
    return rng.sample(pool, n) + list(NEVER_COMMUNICATED)


# ------------------------------------------------------------ atomic publish

def _atomic_csv(directory, filename, columns, rows):
    """Write to a name the forwarder's whitelist does not match, then rename.
    The leading dot also excludes the in-progress file from the blacklist rule,
    so a forwarder can never open a half-written export."""
    os.makedirs(directory, exist_ok=True)
    partial = os.path.join(directory, "." + filename + ".partial")
    final = os.path.join(directory, filename)
    with open(partial, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)  # csv.writer terminates CRLF, as a Windows producer does
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(c, "") for c in columns])
    os.replace(partial, final)
    return final


def _checkpoint(events_dir):
    """The producer's high-water mark. Dot-prefixed so the same rule that
    excludes the in-progress file excludes it: a checkpoint indexed as an event
    is a parse failure nobody reads."""
    return os.path.join(events_dir, ".epo-events.checkpoint")


def publish_csv_cycle(rng, export_root, when=None, n_events=120,
                      systems=False, agent_health=True):
    """Publish one export cycle. Returns the paths published.

    n_events is a demonstration density, not a rate: a real tuned fleet of this
    size produces single-digit detections per day, which fills no panel.
    """
    when = when or datetime.now(timezone.utc)
    events_dir = os.path.join(export_root, "events")
    os.makedirs(events_dir, exist_ok=True)

    cp = _checkpoint(events_dir)
    start = 100000
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as fh:
            start = int(fh.read().strip()) + 1

    rows, rid = [], start
    span = max(n_events, 1)
    for i in range(n_events):
        # Spread detections across the cycle so detected/received lag is a
        # distribution rather than one value repeated.
        offset = timedelta(seconds=(span - i) * (900.0 / span))
        rows.append(event_row(rng, rid, when - offset))
        rid += 1
    max_id = rid - 1

    published = []
    if rows:
        name = f"epo-events-{_stamp(when)}-{max_id}.csv"
        published.append(_atomic_csv(events_dir, name, EVENT_COLUMNS, rows))
        with open(cp, "w", encoding="utf-8") as fh:
            fh.write(str(max_id))

    if systems:
        hosts = _changed_since(rng, when, 0.35)
        published.append(_atomic_csv(
            os.path.join(export_root, "systems"),
            f"epo-systems-{_stamp(when)}.csv",
            SYSTEMS_COLUMNS, systems_rows(rng, hosts, when)))

    if agent_health:
        hosts = _changed_since(rng, when, 0.55)
        published.append(_atomic_csv(
            os.path.join(export_root, "agent_health"),
            f"epo-agent-health-{_stamp(when)}.csv",
            HEALTH_COLUMNS, agent_health_rows(rng, hosts, when)))

    return published


# --------------------------------------------------------- state extracts

STATE_SOURCETYPES = ("winstate:bitlocker", "winstate:bitlocker_escrow",
                     "winstate:auditpol", "nixstate:luks", "nixstate:auditd")

# EncryptionMethod and KeyProtectorType numerics as Win32_EncryptableVolume
# reports them.
ENCRYPTION_METHODS = {4: "AES-256", 6: "XTS-AES-128", 7: "XTS-AES-256"}
KEY_PROTECTORS = {1: "TPM", 3: "NumericalPassword", 4: "TPMAndPIN"}

# The subcategories the in-scope Windows sources depend on. A real
# auditpol /get /category:* carries about sixty; this is the subset whose
# setting decides whether another row in the coverage matrix has any data.
AUDIT_SUBCATEGORIES = [
    ("Account Logon", "Credential Validation", "Success and Failure", True),
    ("Account Logon", "Kerberos Authentication Service", "Success and Failure", False),
    ("Account Logon", "Kerberos Service Ticket Operations", "Success and Failure", False),
    ("Account Management", "User Account Management", "Success and Failure", True),
    ("Account Management", "Security Group Management", "Success and Failure", True),
    ("Account Management", "Computer Account Management", "Success", True),
    ("Detailed Tracking", "Process Creation", "Success", True),
    ("Detailed Tracking", "Process Termination", "No Auditing", True),
    ("DS Access", "Directory Service Access", "Success and Failure", False),
    ("DS Access", "Directory Service Changes", "Success", False),
    ("Logon/Logoff", "Logon", "Success and Failure", True),
    ("Logon/Logoff", "Logoff", "Success", True),
    ("Logon/Logoff", "Account Lockout", "Success and Failure", True),
    ("Logon/Logoff", "Special Logon", "Success", True),
    ("Logon/Logoff", "Other Logon/Logoff Events", "Success and Failure", True),
    ("Object Access", "File System", "Success and Failure", True),
    ("Object Access", "Registry", "Success and Failure", True),
    ("Object Access", "Removable Storage", "Success and Failure", True),
    ("Object Access", "Other Object Access Events", "Success", True),
    ("Policy Change", "Audit Policy Change", "Success", True),
    ("Policy Change", "Authentication Policy Change", "Success", True),
    ("Privilege Use", "Sensitive Privilege Use", "Success and Failure", True),
    ("System", "Security State Change", "Success", True),
    ("System", "Security System Extension", "Success", True),
    ("System", "System Integrity", "Success and Failure", True),
]

# auditctl -l as the compiled rule set prints it, with the key each rule tags.
AUDITD_RULES = [
    "-w /etc/audit/ -p wa -k auditconfig",
    "-w /etc/audit/rules.d/ -p wa -k auditconfig",
    "-w /usr/sbin/auditctl -p x -k audittools",
    "-w /usr/sbin/auditd -p x -k audittools",
    "-w /usr/sbin/augenrules -p x -k audittools",
    "-w /etc/passwd -p wa -k identity",
    "-w /etc/shadow -p wa -k identity",
    "-w /etc/sudoers -p wa -k privileged",
    "-w /etc/sudoers.d/ -p wa -k privileged",
    "-a always,exit -F arch=b64 -S execve -C uid!=euid -F euid=0 -k privileged",
    "-a always,exit -F arch=b64 -S mount -F auid>=1000 -F auid!=-1 -k mount",
    "-a always,exit -F arch=b64 -S unlink,unlinkat,rename,renameat -F auid>=1000 -F auid!=-1 -k delete",
    "-w /var/log/lastlog -p wa -k logins",
    "-w /etc/ssh/sshd_config -p wa -k sshd",
]


def _state_record(extract, host, when, snapshot_id, object_id, fields):
    """collected_at FIRST, because the search-time timestamp is pulled with
    TIME_PREFIX and a long JSON line would otherwise push it past
    MAX_TIMESTAMP_LOOKAHEAD.

    collector_status is a third value beside the answer: a query that could not
    run is not the same as a volume that is not encrypted, and a scripted input
    that writes nothing on failure makes the two indistinguishable.
    """
    rec = {"collected_at": _iso(when), "snapshot_id": snapshot_id,
           "extract": extract, "host": host, "object_id": object_id,
           "collector_status": "ok"}
    rec.update(fields)
    return rec


def state_records(rng, when=None, cadence_days=1):
    """One collection cycle of every state extract.

    Yields (sourcetype, host, record). The whole population is republished every
    cycle, which is the property that makes a sum across a window report the
    population multiplied by the number of collections.
    """
    when = when or datetime.now(timezone.utc)
    snapshot_id = when.strftime("%Y-%m-%d") if cadence_days >= 1 else _iso(when)

    for host in MANAGED:
        yield from _bitlocker_for(rng, host, when, snapshot_id)
    for host in MANAGED:
        yield from _auditpol_for(rng, host, when, snapshot_id)
    for host in MANAGED:
        yield _escrow_for(rng, host, when, snapshot_id)
    for host in environment.LINUX:
        yield from _luks_for(rng, host, when, snapshot_id)
        yield from _auditd_for(rng, host, when, snapshot_id)


def _bitlocker_for(rng, host, when, snapshot_id):
    # Every fixed and removable volume, not the system drive alone: the
    # recurring finding is a protected C: beside an unprotected data volume
    # that nothing ever asked about.
    volumes = [("C:", "OperatingSystem", 256)]
    if host in environment.SERVERS or host in environment.DCS:
        volumes.append(("D:", "Fixed", 1024))
    if host in environment.WORKSTATIONS and rng.random() < 0.35:
        volumes.append(("E:", "Removable", 64))

    for mount, vtype, capacity in volumes:
        protected = not (vtype != "OperatingSystem" and rng.random() < 0.25)
        suspended = protected and rng.random() < 0.06
        method = 7 if protected else 0
        if protected and rng.random() < 0.12:
            method = 4  # legacy AES-256 carried forward from an old image
        protectors = []
        if protected:
            # A volume whose only protector is a numerical recovery password is
            # not in a hardware-protected key store at all, which is the SC-28(3)
            # failure case; without it in the data that assertion never runs.
            if rng.random() < 0.10:
                protectors = [3]
            else:
                protectors = [4] if rng.random() < 0.55 else [1]
                if rng.random() < 0.85:
                    protectors.append(3)
        # A suspended volume reports ConversionStatus 1 with ProtectionStatus 0;
        # an extract carrying only one of the two reports it as compliant.
        yield ("winstate:bitlocker", host, _state_record(
            "bitlocker", host, when, snapshot_id, f"{host}:{mount}", {
                "mount_point": mount,
                "volume_type": vtype,
                "protection_status": 0 if (not protected or suspended) else 1,
                "conversion_status": 1 if protected else 0,
                "encryption_percentage": 100 if protected else 0,
                "encryption_method_id": method,
                "encryption_method": ENCRYPTION_METHODS.get(method, "None"),
                "key_protector_ids": protectors,
                "key_protectors": [KEY_PROTECTORS[p] for p in protectors],
                "hardware_protected_key": any(p in (1, 4) for p in protectors),
                "capacity_gb": capacity,
                "collector": "Get-BitLockerVolume",
            }))


def _escrow_for(rng, host, when, snapshot_id):
    """Recovery key inventory is an AD DS query, not a host query: the
    msFVE-RecoveryInformation objects live under the computer object and no
    endpoint extract can see them."""
    keys = 0 if rng.random() < 0.08 else rng.randrange(1, 4)
    return ("winstate:bitlocker_escrow", environment.DCS[0], _state_record(
        "bitlocker_escrow", environment.DCS[0], when, snapshot_id, host, {
            "computer": host,
            "computer_dn": f"CN={host},OU=Endpoints,DC=" +
                           ",DC=".join(environment.DOMAIN.split(".")),
            "recovery_key_count": keys,
            "newest_recovery_key_created": "" if not keys else _iso(
                when - timedelta(days=rng.randrange(1, 400))),
            "collector": "Get-ADObject msFVE-RecoveryInformation",
        }))


def _auditpol_for(rng, host, when, snapshot_id):
    is_dc = host in environment.DCS
    # One host deliberately without the override set. A legacy category setting
    # anywhere in the GPO stack then silently overwrites every subcategory, and
    # the Resultant Set of Policy report never shows it.
    override = 0 if host == environment.WORKSTATIONS[5] else 1
    degraded = host in (environment.WORKSTATIONS[2], environment.SERVERS[1])

    applied = []
    for category, subcategory, setting, member_scope in AUDIT_SUBCATEGORIES:
        if not member_scope and not is_dc:
            setting = "No Auditing"
        if degraded and subcategory in ("Process Creation", "Removable Storage"):
            setting = "No Auditing"
        applied.append((category, subcategory, setting))

    # A digest over the sorted pairs makes a changed policy a single equality
    # test, which is what lets a daily cycle publish a digest instead of sixty
    # rows once the fleet is large.
    digest = hashlib.sha256(
        "\n".join(f"{c}|{s}|{v}" for c, s, v in sorted(applied)).encode()).hexdigest()

    yield ("winstate:auditpol", host, _state_record(
        "auditpol", host, when, snapshot_id, f"{host}:_host", {
            "record_type": "host",
            "policy_digest": digest,
            "sce_no_apply_legacy_audit_policy": override,
            "crash_on_audit_fail": 0,
            "process_creation_include_cmdline_enabled": 0 if degraded else 1,
            "powershell_scriptblock_logging": 1,
            "powershell_module_logging": 1,
            "channel_security_max_kb": 1024000 if not degraded else 20480,
            "channel_system_max_kb": 32768,
            "channel_powershell_operational_max_kb": 131072,
            "host_class": "domain_controller" if is_dc else
                          ("member_server" if host in environment.SERVERS else "workstation"),
            "collector": "auditpol /get /category:* /r",
        }))

    for category, subcategory, setting in applied:
        yield ("winstate:auditpol", host, _state_record(
            "auditpol", host, when, snapshot_id, f"{host}:{subcategory}", {
                "record_type": "subcategory",
                "category": category,
                "subcategory": subcategory,
                "setting": setting,
                "policy_digest": digest,
            }))


def _luks_for(rng, host, when, snapshot_id):
    # Enumeration is driven from lsblk and dmsetup rather than from
    # /etc/crypttab: a plain dm-crypt mapping carries no header and a device
    # absent from crypttab is exactly the one at issue.
    fips = host == environment.LINUX[0]
    devices = [("/dev/sda2", "root", True), ("/dev/sda3", "swap", True),
               ("/dev/sdb1", "data", host != environment.LINUX[2]),
               ("/dev/sdc1", "container-pool", False)]

    # One host where the collection has no privilege. Recorded rather than
    # omitted: an absent row and an unencrypted volume must not read the same.
    if host == environment.LINUX[1]:
        yield ("nixstate:luks", host, _state_record(
            "luks", host, when, snapshot_id, f"{host}:/dev/sdd1", {
                "collector_status": "denied",
                "device": "/dev/sdd1",
                "detail": "cryptsetup luksDump: Operation not permitted",
                "collector": "cryptsetup luksDump",
            }))

    for device, mapping, encrypted in devices:
        if not encrypted:
            # The negative case recorded explicitly. An unencrypted volume emits
            # no events at all, which is precisely the case SC-28 exists to catch.
            yield ("nixstate:luks", host, _state_record(
                "luks", host, when, snapshot_id, f"{host}:{device}", {
                    "device": device,
                    "fstype": "xfs",
                    "encrypted": False,
                    "luks_version": "",
                    "cipher": "",
                    "key_size": "",
                    "pbkdf": "",
                    "key_slots_used": 0,
                    "fips_enabled": int(fips),
                    "collector": "lsblk + dmsetup table --target crypt",
                }))
            continue
        yield ("nixstate:luks", host, _state_record(
            "luks", host, when, snapshot_id, f"{host}:{device}", {
                "device": device,
                "mapping": mapping,
                "fstype": "crypto_LUKS",
                "encrypted": True,
                "luks_version": "2",
                "cipher": "aes-xts-plain64",
                "key_size": 512,
                # With fips_enabled set, cryptsetup uses PBKDF2 rather than
                # Argon2id, so a FIPS host and a non-FIPS host legitimately
                # differ and an unexplained difference is a finding either way.
                "pbkdf": "pbkdf2" if fips else "argon2id",
                "key_slots_used": 1 if rng.random() > 0.2 else 2,
                "clevis_binding": "tpm2" if host == environment.LINUX[1] else "",
                "fips_enabled": int(fips),
                "collector": "cryptsetup luksDump",
            }))


def _auditd_for(rng, host, when, snapshot_id):
    immutable = host != environment.LINUX[2]
    lost = 0 if rng.random() > 0.15 else rng.randrange(1, 900)
    rules = list(AUDITD_RULES)
    if host == environment.LINUX[2]:
        rules = rules[:8]
    digest = hashlib.sha256("\n".join(rules).encode()).hexdigest()

    yield ("nixstate:auditd", host, _state_record(
        "auditd", host, when, snapshot_id, f"{host}:_status", {
            "record_type": "status",
            "enabled": 2 if immutable else 1,
            # -f 1 only prints to the kernel log, so a host set to -f 1 does not
            # respond to audit failure however the SSP describes it.
            "failure": 2 if immutable else 1,
            "pid": rng.randrange(700, 1400),
            "rate_limit": 0,
            "backlog_limit": 8192,
            "lost": lost,
            "backlog": rng.randrange(0, 64),
            "backlog_wait_time": 60000,
            "augenrules_check": "No change" if rng.random() > 0.1 else "rules differ",
            "rules_digest": digest,
            "rule_count": len(rules),
            "collector": "auditctl -s; augenrules --check",
        }))

    for rule in rules:
        yield ("nixstate:auditd", host, _state_record(
            "auditd", host, when, snapshot_id,
            f"{host}:{hashlib.sha256(rule.encode()).hexdigest()[:16]}", {
                "record_type": "rule",
                "rule": rule,
                "rule_key": rule.split("-k ")[-1] if "-k " in rule else "",
                "rules_digest": digest,
                "collector": "auditctl -l",
            }))


def publish_state_cycle(rng, state_dir, when=None):
    """Write one cycle per sourcetype, one JSON object per line.

    A production scripted input writes to stdout and has no file, so there is no
    file tracker and no re-index hazard at all. The lab uses files only so a
    universal forwarder can tail them.
    """
    when = when or datetime.now(timezone.utc)
    os.makedirs(state_dir, exist_ok=True)
    handles, counts = {}, {}
    try:
        for sourcetype, host, record in state_records(rng, when):
            if sourcetype not in handles:
                path = os.path.join(state_dir, sourcetype.replace(":", "_") + ".log")
                handles[sourcetype] = open(path, "a", buffering=1, encoding="utf-8")
            handles[sourcetype].write(json.dumps(record, separators=(",", ":")) + "\n")
            counts[sourcetype] = counts.get(sourcetype, 0) + 1
    finally:
        for fh in handles.values():
            fh.close()
    return counts


# ------------------------------------------------------------------- driver

def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--export-root", required=True,
                    help="the directory the forwarder monitors: <root>/events, /systems, /agent_health")
    ap.add_argument("--state-dir", help="where the state extract lines are written")
    # More than one state cycle is what makes the multiplication visible: the
    # whole population is republished every cycle, so an unreduced count over
    # the window is the population times this number.
    ap.add_argument("--state-cycles", type=int, default=1)
    ap.add_argument("--state-interval-hours", type=int, default=24)
    ap.add_argument("--cycles", type=int, default=1)
    ap.add_argument("--events-per-cycle", type=int, default=120)
    ap.add_argument("--interval-minutes", type=int, default=15)
    ap.add_argument("--seed", type=int, default=1729)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    now = datetime.now(timezone.utc)
    for i in range(args.cycles):
        when = now - timedelta(minutes=args.interval_minutes * (args.cycles - 1 - i))
        # The inventory is the expensive query and changes slowly, so it runs on
        # the first cycle of the run rather than on every one.
        paths = publish_csv_cycle(rng, args.export_root, when,
                                  n_events=args.events_per_cycle,
                                  systems=(i == 0), agent_health=True)
        for path in paths:
            print(f"published {path}", flush=True)
    if args.state_dir:
        total = {}
        for i in range(args.state_cycles):
            when = now - timedelta(hours=args.state_interval_hours *
                                   (args.state_cycles - 1 - i))
            for sourcetype, n in publish_state_cycle(rng, args.state_dir, when).items():
                total[sourcetype] = total.get(sourcetype, 0) + n
        for sourcetype in sorted(total):
            print(f"state {sourcetype} {total[sourcetype]} rows over "
                  f"{args.state_cycles} cycle(s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
