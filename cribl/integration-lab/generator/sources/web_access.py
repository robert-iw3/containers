"""
IIS and nginx access logs from the environment's web tier.

Combined-format access lines. Security reads the 4xx/5xx and the odd
user-agent; everything else is capacity data that a SIEM license is an
expensive place to keep.
"""

import random
import environment

KEY = "web_access"
SOURCETYPE = "access_combined"
SOURCE = "/var/log/nginx/access.log"
SHARE = 6.0

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = "status"

CONTROLS = [
    ("AU-12", "CSF DE.CM-01", ["401", "403", "404", "500"], False, "audit generation for web tier"),
    ("SI-4",  "CSF DE.CM-01", ["401", "403", "404", "500"], True,  "monitoring for web attack patterns"),
    ("SC-7",  "CSF PR.IR-01", ["403"], True, "boundary protection at the application edge"),
]
DROPPED_BY_DESIGN = []

PATHS = ["/", "/api/v2/orders", "/static/app.4f2c.js", "/health", "/api/v2/customers",
         "/assets/logo.svg", "/login", "/api/v2/reports?range=30d"]


def emit(rng, host, record_id, ts):
    status = rng.choices([200, 204, 301, 302, 401, 403, 404, 500],
                         weights=[74, 6, 4, 3, 3, 2, 6, 2], k=1)[0]
    ip = rng.choice(environment.EXTERNAL_HOSTS + [environment.ip_for(w) for w in environment.WORKSTATIONS[:5]])
    raw = (f'{ip} - {rng.choice(environment.USERS) if status in (401,403) else "-"} [{ts}] '
           f'"{rng.choice(["GET","GET","GET","POST"])} {rng.choice(PATHS)} HTTP/1.1" '
           f'{status} {rng.randrange(120, 900000)} "https://intranet.{environment.DOMAIN}/" '
           f'"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
           f'Chrome/140.0.0.0 Safari/537.36" {rng.randrange(1,4000)}')
    return raw, {"status": status}
