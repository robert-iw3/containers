"""
Palo Alto PAN-OS TRAFFIC and THREAT logs.

Comma-separated syslog in PAN-OS field order. Firewall traffic is normally the
largest single feed in a SIEM and is almost entirely session records that no
detection reads, which is why it is the canonical Cribl reduction target: trim
the unused columns and aggregate the allowed sessions, keep every deny and
every threat.
"""

import random
import environment

KEY = "pan_firewall"
SOURCETYPE = "pan:traffic"
SOURCE = "pan_fw01"
SHARE = 21.0

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = "pan_type"

CONTROLS = [
    ("SC-7",  "CSF PR.IR-01", ["THREAT", "TRAFFIC"], True,  "boundary protection"),
    ("SI-4",  "CSF DE.CM-01", ["THREAT", "TRAFFIC"], True,  "system monitoring at the boundary"),
    ("AU-12", "CSF DE.CM-01", ["TRAFFIC"], False, "audit generation; allowed sessions are aggregatable"),
    ("AC-17", "CSF PR.AA-05", ["TRAFFIC"], True, "remote access monitoring"),
]
DROPPED_BY_DESIGN = []

APPS = ["ssl", "web-browsing", "dns", "ms-update", "office365-enterprise-access",
        "ldap", "kerberos", "smb", "ssh", "quic"]
RULES = ["allow-internal-out", "allow-web", "allow-dns", "deny-any-any", "vpn-users-out"]
THREATS = [("spyware", "Suspicious DNS Query (generic:paste.ee)", "medium"),
           ("vulnerability", "Microsoft Windows SMB Remote Code Execution", "critical"),
           ("virus", "Trojan/Win32.emotet", "high"),
           ("url-filtering", "malware-sites", "high")]


def emit(rng, host, record_id, ts):
    threat = rng.random() < 0.02
    src_host = rng.choice(environment.WORKSTATIONS + environment.SERVERS)
    src = environment.ip_for(src_host)
    dst = rng.choice(environment.EXTERNAL_HOSTS)
    action = "deny" if rng.random() < 0.06 else "allow"
    app = rng.choice(APPS)
    sport, dport = rng.randrange(1024, 65535), rng.choice([443, 443, 80, 53, 445, 22, 389])
    pkts_s, pkts_r = rng.randrange(1, 400), rng.randrange(1, 900)
    bytes_s, bytes_r = pkts_s * rng.randrange(60, 1400), pkts_r * rng.randrange(60, 1400)
    if threat:
        ttype, tname, sev = rng.choice(THREATS)
        raw = (f"1,{ts},014101010001,THREAT,{ttype},2561,{ts},{src},{dst},"
               f"{src},{dst},{rng.choice(RULES)},{rng.choice(environment.USERS)},,{app},vsys1,"
               f"trust,untrust,ae1.100,ae2.200,LOG-PROFILE,{ts},{record_id},1,"
               f"{sport},{dport},{sport},{dport},0x400000,tcp,{action},"
               f"\"{tname}\",{record_id},{sev},client-to-server,{record_id},0x0,"
               f"10.0.0.0-10.255.255.255,United States,,,0,,0,,N/A,{ttype},AppThreat-8790-8462,"
               f"0x0,0,4294967295,,,{src_host},,,,,,,,,,,,,,,,,,,,,")
        meta = {"kind": "threat", "severity": sev, "action": action}
    else:
        raw = (f"1,{ts},014101010001,TRAFFIC,end,2561,{ts},{src},{dst},"
               f"{src},{dst},{rng.choice(RULES)},{rng.choice(environment.USERS)},,{app},vsys1,"
               f"trust,untrust,ae1.100,ae2.200,LOG-PROFILE,{ts},{record_id},1,"
               f"{sport},{dport},{sport},{dport},0x400053,tcp,{action},"
               f"{bytes_s + bytes_r},{bytes_s},{bytes_r},{pkts_s + pkts_r},{ts},"
               f"{rng.randrange(1, 900)},any,0,{record_id},0x8000,"
               f"10.0.0.0-10.255.255.255,United States,,{pkts_s},{pkts_r},"
               f"tcp-fin,0,0,0,0,,PA-5220,from-policy,,,0,,0,,N/A,N/A,N/A,N/A,"
               f"{ts},0,0,0,0,,{src_host},,,,,,,,,,,,,,,,,,")
        meta = {"kind": "traffic", "action": action}
    meta["src"] = src
    return raw, meta
