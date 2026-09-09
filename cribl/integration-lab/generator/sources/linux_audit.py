"""
Linux servers: sshd and auditd over syslog.

The environment's Linux tier. Small share of volume, large share of the controls
that ask about privileged access on servers.
"""

import random
import environment

KEY = "linux_audit"
SOURCETYPE = "linux_secure"
SOURCE = "/var/log/secure"
SHARE = 0.7

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = None

CONTROLS = [
    ("AC-6(9)", "CSF PR.AA-05", ["sudo", "USER_CMD"], True, "auditing of privileged functions"),
    ("AC-7",   "CSF DE.CM-01", ["Failed password"], True,  "unsuccessful logon attempts"),
    ("AC-17",  "CSF PR.AA-05", ["Accepted publickey"], True, "remote access"),
    ("IA-2",   "CSF PR.AA-02", ["Accepted publickey", "Failed password"], True, "identification and authentication"),
    ("AU-12",  "CSF DE.CM-01", ["CRED_ACQ", "USER_START"], True, "audit generation"),
]
DROPPED_BY_DESIGN = []


def emit(rng, host, record_id, ts):
    srv = rng.choice(environment.LINUX)
    user = rng.choice(environment.USERS)
    ip = environment.ip_for(rng.choice(environment.WORKSTATIONS))
    r = rng.random()
    if r < 0.10:
        raw = (f"{ts} {srv} sshd[{rng.randrange(1000,60000)}]: Failed password for "
               f"{'invalid user ' if rng.random()<0.3 else ''}{user} from {ip} "
               f"port {rng.randrange(1024,65535)} ssh2")
        kind = "auth_fail"
    elif r < 0.25:
        raw = (f"{ts} {srv} sshd[{rng.randrange(1000,60000)}]: Accepted publickey for {user} "
               f"from {ip} port {rng.randrange(1024,65535)} ssh2: RSA "
               f"SHA256:{record_id:043X}")
        kind = "auth_ok"
    elif r < 0.35:
        raw = (f"{ts} {srv} sudo: {user} : TTY=pts/{rng.randrange(0,4)} ; "
               f"PWD=/home/{user} ; USER=root ; COMMAND=/usr/bin/systemctl restart nginx")
        kind = "sudo"
    else:
        raw = (f"{ts} {srv} audispd: node={srv} type=SYSCALL "
               f"msg=audit({record_id}.{rng.randrange(100,999)}:{record_id}): arch=c000003e "
               f"syscall=59 success=yes exit=0 a0=55d1 a1=55d2 a2=55d3 a3=0 items=2 "
               f"ppid={rng.randrange(1,9000)} pid={rng.randrange(1,60000)} auid={rng.randrange(1000,1010)} "
               f"uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=pts0 "
               f"ses={rng.randrange(1,900)} comm=\"bash\" exe=\"/usr/bin/bash\" "
               f"key=\"privileged\"")
        kind = "auditd"
    return raw, {"kind": kind}
