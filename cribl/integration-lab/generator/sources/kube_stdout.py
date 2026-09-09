"""
Container stdout from the Kubernetes platform.

Application logging that reaches the SIEM because it was easier to forward
everything than to decide. Mostly INFO lines no detection reads; a small tail
of WARN and ERROR that operations genuinely needs. Included because the honest
version of the Cribl argument is about routing this somewhere cheaper, not
about deleting it.
"""

import json
import random
import environment

KEY = "kube_stdout"
SOURCETYPE = "kube:container:app"
SOURCE = "/var/log/containers"
SHARE = 8.0

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = "level"

CONTROLS = [
    ("AU-12", "CSF DE.CM-01", ["ERROR", "WARN"], False, "application audit records; INFO is operational"),
    ("SI-4",  "CSF DE.CM-01", ["ERROR"], False, "monitoring; error lines only"),
]
DROPPED_BY_DESIGN = []

LEVELS = [(86, "INFO"), (9, "WARN"), (4, "ERROR"), (1, "DEBUG")]
_W = [l[0] for l in LEVELS]
_L = [l[1] for l in LEVELS]
MSGS = {
    "INFO": ["handled request", "cache refreshed", "healthcheck ok", "scheduled job complete"],
    "WARN": ["retrying upstream", "slow query", "connection pool at capacity"],
    "ERROR": ["upstream timeout", "failed to persist record", "unhandled rejection"],
    "DEBUG": ["entering handler", "span closed"],
}


def emit(rng, host, record_id, ts):
    lvl = rng.choices(_L, weights=_W, k=1)[0]
    ns = rng.choice(["payments", "identity", "web", "batch"])
    rec = {"timestamp": ts, "level": lvl, "logger": f"com.example.{ns}.Handler",
           "thread": f"http-nio-8080-exec-{rng.randrange(1,32)}",
           "message": rng.choice(MSGS[lvl]),
           "traceId": f"{record_id:032x}", "spanId": f"{record_id:016x}",
           "kubernetes": {"namespace_name": ns,
                          "pod_name": f"{ns}-{rng.randrange(10**8,10**9)}-{rng.randrange(10**4,10**5)}",
                          "container_name": ns, "host": rng.choice(environment.LINUX)},
           "durationMs": rng.randrange(1, 4000), "status": 200 if lvl == "INFO" else 500}
    return json.dumps(rec), {"level": lvl, "namespace": ns}
