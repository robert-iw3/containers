"""
Cisco ISE: 802.1X and VPN authentication, the identity edge of the network.

ISE is verbose by default - a single successful authentication emits several
records - and most of the volume is the passed-authentication detail that no
detection reads. The failures and the posture results are what matter.
"""

import random
import environment

KEY = "cisco_ise"
SOURCETYPE = "cisco:ise:syslog"
SOURCE = "ise-psn-01"
SHARE = 3.0

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = None

CONTROLS = [
    ("IA-2",   "CSF PR.AA-02", ["CISE_Passed_Authentications", "CISE_Failed_Attempts"], True, "identification and authentication of users and devices"),
    ("AC-7",   "CSF DE.CM-01", ["CISE_Failed_Attempts"], True, "unsuccessful logon attempts"),
    ("AC-17",  "CSF PR.AA-05", ["CISE_Passed_Authentications"], True, "remote access authentication"),
    ("IA-3",   "CSF PR.AA-01", ["CISE_Passed_Authentications"], True, "device identification and authentication"),
    ("CM-8",   "CSF ID.AM-01", ["CISE_Profiler"], False, "component inventory via profiling"),
]
DROPPED_BY_DESIGN = []


def emit(rng, host, record_id, ts):
    ok = rng.random() > 0.08
    user = rng.choice(environment.USERS)
    dev = rng.choice(environment.WORKSTATIONS)
    mac = environment.mac_for(dev)
    cat = "CISE_Passed_Authentications" if ok else "CISE_Failed_Attempts"
    code = "5200 NOTICE Passed-Authentication: Authentication succeeded" if ok else \
           "5400 NOTICE Failed-Attempt: Authentication failed"
    raw = (f"<181>{ts} ise-psn-01 {cat} 0000{record_id % 100000:06d} 1 0 "
           f"{ts}, {rng.randrange(100000,999999)}, {rng.randrange(1,9)}, NOTICE, "
           f"{code}, ConfigVersionId={rng.randrange(10,99)}, "
           f"Device IP Address={environment.ip_for('SW-ACC-01')}, "
           f"DestinationIPAddress={environment.ip_for('ise-psn-01')}, DestinationPort=1812, "
           f"UserName={user}, Protocol=Radius, RequestLatency={rng.randrange(3,90)}, "
           f"NetworkDeviceName=SW-ACC-01, User-Name={user}, NAS-IP-Address={environment.ip_for('SW-ACC-01')}, "
           f"NAS-Port={rng.randrange(1,48)}, Service-Type=Framed, Framed-MTU=1500, "
           f"Called-Station-ID={mac}, Calling-Station-ID={mac}, "
           f"NAS-Port-Type=Ethernet, NAS-Port-Id=GigabitEthernet1/0/{rng.randrange(1,48)}, "
           f"EapAuthentication=EAP-TLS, AuthenticationIdentityStore=AD-corp, "
           f"AuthenticationMethod=x509_PKI, SelectedAccessService=Default Network Access, "
           f"SelectedAuthorizationProfiles={'CorpAccess' if ok else 'Quarantine'}, "
           f"IdentityGroup=Endpoint Identity Groups:Workstations, "
           f"Step=11001, Step=11017, Step=15049, Step=15008, Step=11507, Step=12500, "
           f"Step=12625, Step=12800, Step=12805, Step=12806, Step=12807, Step=12810, "
           f"Step=12811, Step=12505, Step=11006, Step=11001, Step=11018, Step=12504, "
           f"NetworkDeviceGroups=Location#All Locations#HQ, "
           f"CPMSessionID={mac.replace(':','')}{record_id:08X}, "
           f"EndPointMACAddress={mac}, PostureAssessmentStatus={'Compliant' if ok else 'NonCompliant'}")
    return raw, {"passed": ok, "user": user}
