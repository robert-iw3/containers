"""
Suricata EVE JSON: IDS alerts plus the flow records around them.

Alerts are rare and precious; flow and http records are the bulk. The point the
data set makes is that a pipeline can keep every alert and still remove most of
the bytes, because the bytes are not in the alerts.
"""

import json
import random
import environment

KEY = "suricata"
SOURCETYPE = "suricata"
SOURCE = "/var/log/suricata/eve.json"
SHARE = 7.0

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = "eve_type"

CONTROLS = [
    ("SI-4",   "CSF DE.CM-01", ["alert"], True,  "system monitoring, intrusion detection"),
    ("SI-4(4)", "CSF DE.CM-09", ["alert", "flow"], True, "inbound and outbound traffic monitoring"),
    ("SC-7",   "CSF PR.IR-01", ["alert"], True,  "boundary protection"),
    ("AU-12",  "CSF DE.AE-03", ["flow", "http"], False, "audit generation; flow is aggregatable"),
]
DROPPED_BY_DESIGN = []

SIGS = [
    (2024897, "ET MALWARE Observed DNS Query to Suspicious Domain", "A Network Trojan was detected", 1),
    (2018959, "ET POLICY PE EXE or DLL Windows file download HTTP", "Potential Corporate Privacy Violation", 2),
    (2027865, "ET EXPLOIT SMB RCE Attempt", "Attempted Administrator Privilege Gain", 1),
    (2013028, "ET POLICY curl User-Agent Outbound", "Not Suspicious Traffic", 3),
]


def emit(rng, host, record_id, ts):
    sensor = "ids-core-01"
    src_host = rng.choice(environment.WORKSTATIONS)
    src, dst = environment.ip_for(src_host), rng.choice(environment.EXTERNAL_HOSTS)
    sport, dport = rng.randrange(1024, 65535), rng.choice([443, 80, 445, 53])
    base = {"timestamp": ts, "flow_id": rng.randrange(10**12, 10**13), "in_iface": "eth0",
            "src_ip": src, "src_port": sport, "dest_ip": dst, "dest_port": dport,
            "proto": "TCP", "host": sensor}
    r = rng.random()
    if r < 0.015:
        sid, msg, cat, sev = rng.choice(SIGS)
        base.update({"event_type": "alert",
                     "alert": {"action": "allowed", "gid": 1, "signature_id": sid, "rev": 3,
                               "signature": msg, "category": cat, "severity": sev},
                     "app_proto": "http" if dport == 80 else "tls"})
        kind = "alert"
    elif r < 0.35:
        base.update({"event_type": "http",
                     "http": {"hostname": rng.choice(environment.DNS_COMMON), "url": "/updates/manifest.json",
                              "http_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                              "http_method": "GET", "protocol": "HTTP/1.1", "status": 200,
                              "length": rng.randrange(200, 90000)}})
        kind = "http"
    else:
        base.update({"event_type": "flow",
                     "flow": {"pkts_toserver": rng.randrange(1, 300), "pkts_toclient": rng.randrange(1, 400),
                              "bytes_toserver": rng.randrange(60, 200000), "bytes_toclient": rng.randrange(60, 900000),
                              "start": ts, "end": ts, "age": rng.randrange(0, 300),
                              "state": "closed", "reason": "timeout", "alerted": False}})
        kind = "flow"
    return json.dumps(base), {"kind": kind}
