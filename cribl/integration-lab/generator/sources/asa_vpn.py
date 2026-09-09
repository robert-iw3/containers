"""
Cisco ASA, including the AnyConnect VPN messages.

ASA emits one syslog line per session event with a %ASA-level-id header. The
session teardown lines carry the byte counts and are the bulk; the VPN
connect/disconnect and the denies are what a control needs.
"""

import random
import environment

KEY = "asa_vpn"
SOURCETYPE = "cisco:asa"
SOURCE = "asa-vpn-01"
SHARE = 1.0

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = "asa_id"

CONTROLS = [
    ("AC-17",  "CSF PR.AA-05", ["113039", "722051", "113019"], True, "remote access, monitored and controlled"),
    ("AC-17(1)", "CSF PR.AA-05", ["113039", "722051"], True, "automated monitoring of remote access"),
    ("SC-7",   "CSF PR.IR-01", ["106023"], True, "boundary protection, denied traffic"),
    ("AU-12",  "CSF DE.CM-01", ["302014"], False, "audit generation; session records are aggregatable"),
    ("MA-4",   "CSF PR.AA-05", ["113039"], True, "nonlocal maintenance sessions"),
]
DROPPED_BY_DESIGN = []


def emit(rng, host, record_id, ts):
    user = rng.choice(environment.USERS)
    ip = rng.choice(environment.EXTERNAL_HOSTS)
    assigned = f"10.99.{rng.randrange(1,20)}.{rng.randrange(2,250)}"
    r = rng.random()
    if r < 0.02:
        raw = (f"<166>{ts} asa-vpn-01 : %ASA-4-113039: Group <CorpVPN> User <{user}> "
               f"IP <{ip}> AnyConnect parent session started.")
        kind = "vpn_start"
    elif r < 0.04:
        raw = (f"<166>{ts} asa-vpn-01 : %ASA-4-722051: Group <CorpVPN> User <{user}> "
               f"IP <{ip}> IPv4 Address <{assigned}> IPv6 address <::> assigned to session")
        kind = "vpn_assign"
    elif r < 0.06:
        raw = (f"<166>{ts} asa-vpn-01 : %ASA-4-113019: Group = CorpVPN, Username = {user}, "
               f"IP = {ip}, Session disconnected. Session Type: SSL, Duration: "
               f"{rng.randrange(1,9)}h:{rng.randrange(0,59):02d}m:{rng.randrange(0,59):02d}s, "
               f"Bytes xmt: {rng.randrange(10**4,10**8)}, Bytes rcv: {rng.randrange(10**4,10**8)}, "
               f"Reason: User Requested")
        kind = "vpn_end"
    elif r < 0.12:
        raw = (f"<164>{ts} asa-vpn-01 : %ASA-4-106023: Deny tcp src outside:{ip}/{rng.randrange(1024,65535)} "
               f"dst inside:{environment.ip_for(rng.choice(environment.SERVERS))}/{rng.choice([445,3389,22])} "
               f"by access-group \"outside_access_in\" [0x0, 0x0]")
        kind = "deny"
    else:
        src = environment.ip_for(rng.choice(environment.WORKSTATIONS))
        raw = (f"<166>{ts} asa-vpn-01 : %ASA-6-302014: Teardown TCP connection {record_id} "
               f"for outside:{ip}/{rng.choice([443,80])} to inside:{src}/{rng.randrange(1024,65535)} "
               f"duration 0:0{rng.randrange(0,9)}:{rng.randrange(10,59)} "
               f"bytes {rng.randrange(200,900000)} TCP FINs")
        kind = "teardown"
    return raw, {"kind": kind}
