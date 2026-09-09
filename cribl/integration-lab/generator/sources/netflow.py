"""
NetFlow v9 / IPFIX records, as Splunk Stream or a collector renders them.

Pure telemetry: one record per flow, no message, no user, no verdict. It is
routinely 5-10% of a SIEM's licensed volume and is the clearest case of data
that belongs in a metrics store or cheap object storage rather than in a
search-time index.
"""

import random
import environment

KEY = "netflow"
SOURCETYPE = "cisco:netflow"
SOURCE = "netflow:9995"
SHARE = 9.0

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = None

CONTROLS = [
    ("SC-7",   "CSF PR.IR-01", ["flow"], False, "boundary protection; aggregatable to per-pair counters"),
    ("SI-4(4)", "CSF DE.CM-09", ["flow"], False, "traffic monitoring; retained as metrics, not events"),
    ("AU-12",  "CSF DE.CM-01", ["flow"], False, "audit generation"),
]
DROPPED_BY_DESIGN = []


def emit(rng, host, record_id, ts):
    src = environment.ip_for(rng.choice(environment.WORKSTATIONS + environment.SERVERS))
    dst = rng.choice(environment.EXTERNAL_HOSTS + [environment.ip_for(d) for d in environment.DCS])
    raw = (f"{ts},{src},{rng.randrange(1024,65535)},{dst},{rng.choice([443,80,53,445,389])},"
           f"6,{rng.randrange(1,4000)},{rng.randrange(60,4000000)},"
           f"{rng.randrange(0,3)},{rng.randrange(0,63)},0,0,"
           f"{environment.ip_for('core-sw01')},{rng.randrange(1,48)},{rng.randrange(1,48)},"
           f"{rng.choice([0,16,24])},{rng.choice([0,16,24])},0,0,0x1b,{ts},{ts}")
    return raw, {"src": src, "dst": dst}
