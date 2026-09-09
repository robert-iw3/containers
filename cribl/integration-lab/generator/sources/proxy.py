"""
Web proxy access log, squid-native shape.

One line per request, and a browser makes many. Almost pure volume: the
detections that read proxy data read the rare destinations, not the CDN
fetches, so this is where field-trimming and category-based routing pay.
"""

import random
import environment

KEY = "proxy"
SOURCETYPE = "squid:access"
SOURCE = "/var/log/squid/access.log"
SHARE = 5.0

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = "proxy_code"

CONTROLS = [
    ("SC-7",  "CSF PR.IR-01", ["TCP_DENIED"], True,  "boundary protection, blocked requests"),
    ("SI-4",  "CSF DE.CM-01", ["TCP_DENIED", "TCP_MISS"], True, "monitoring outbound traffic"),
    ("AC-4",  "CSF PR.IR-01", ["TCP_DENIED"], True,  "information flow enforcement"),
    ("AU-12", "CSF DE.CM-01", ["TCP_MISS"], False, "audit generation; cache hits are aggregatable"),
]
DROPPED_BY_DESIGN = []

CATS = ["Business", "Technology", "Search Engines", "Content Delivery",
        "Uncategorised", "Malware Sites", "Personal Storage"]


def emit(rng, host, record_id, ts):
    who = rng.choice(environment.WORKSTATIONS)
    denied = rng.random() < 0.04
    cat = rng.choice(CATS[-2:]) if denied else rng.choice(CATS[:5])
    code = "TCP_DENIED/403" if denied else rng.choice(["TCP_MISS/200", "TCP_HIT/200", "TCP_TUNNEL/200"])
    dom = rng.choice(environment.DNS_RARE if denied else environment.DNS_COMMON)
    raw = (f"{ts} {rng.randrange(1,9000):6d} {environment.ip_for(who)} {code} "
           f"{rng.randrange(200,900000)} {'CONNECT' if 'TUNNEL' in code else 'GET'} "
           f"https://{dom}/{'' if denied else 'assets/v2/bundle.js'} "
           f"{rng.choice(environment.USERS)} HIER_DIRECT/{rng.choice(environment.EXTERNAL_HOSTS)} "
           f"text/html \"{cat}\" \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
           f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36\"")
    return raw, {"denied": denied, "category": cat}
