"""
Windows DHCP server audit log, from the domain controllers.

Small, dull, and the only thing in most environments that maps an address to a
machine name and a MAC at a point in time. CM-8 asks for a component inventory;
this is what actually evidences it, and it is routinely dropped in a volume
exercise because nobody searches it until an investigation needs it.
"""

import random
import environment

KEY = "win_dhcp"
SOURCETYPE = "DhcpSrvLog"
SOURCE = "DhcpSrvLog"
SHARE = 0.2

CONTROL_FIELD = "dhcp_id"

CONTROLS = [
    ("CM-8",   "CSF ID.AM-01", ["10", "11", "12"], True, "system component inventory, address to host mapping"),
    ("AU-12",  "CSF DE.CM-01", ["10", "11"], True, "audit generation for address assignment"),
    ("IA-3",   "CSF PR.AA-01", ["10"], True, "device identification and authentication"),
]
DROPPED_BY_DESIGN = []

IDS = [(52, 11, "Renew"), (18, 10, "Assign"), (12, 12, "Release"),
       (10, 15, "NACK"), (8, 30, "DNS update request")]
_W = [i[0] for i in IDS]
_I = [(i[1], i[2]) for i in IDS]


def emit(rng, host, record_id, ts):
    eid, desc = rng.choices(_I, weights=_W, k=1)[0]
    who = rng.choice(environment.WORKSTATIONS)
    raw = (f"{eid},{ts},{desc},{environment.ip_for(who)},{who}.{environment.DOMAIN},"
           f"{environment.mac_for(who).replace(':','')},,{rng.randrange(1000,9999)},0,"
           f"0x0,,,,0x0,,,,0")
    return raw, {"dhcp_id": eid, "host": who}
