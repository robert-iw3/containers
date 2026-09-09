"""
Sysmon operational channel.

Event 3 (network connection) is the volume; events 1, 11 and 22 are the ones
detections are written against. Same argument as the Security channel, on a
channel a mature environment deploys deliberately.
"""

import random
import environment

KEY = "sysmon"
SOURCETYPE = "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational"
SOURCE = "WinEventLog:Microsoft-Windows-Sysmon/Operational"
SHARE = 4.0

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = "EventID"

CONTROLS = [
    ("SI-4",  "CSF DE.CM-01", [1, 3, 11, 22], True,  "system monitoring"),
    ("CM-7",  "CSF PR.PS-02", [1], True,  "least functionality, process execution"),
    ("SI-7",  "CSF PR.DS-06", [11], True, "file integrity"),
    ("SC-7",  "CSF PR.IR-01", [3], False, "network connections; aggregatable"),
    ("AU-12", "CSF DE.CM-01", [1, 3], False, "audit generation"),
]
DROPPED_BY_DESIGN = []

MIX = [(58, 3, "Network connection"), (14, 11, "File created"),
       (12, 1, "Process create"), (8, 22, "DNS query"),
       (4, 13, "Registry value set"), (2, 7, "Image loaded"),
       (1, 8, "CreateRemoteThread"), (1, 10, "Process access")]
_W = [m[0] for m in MIX]
_E = [(m[1], m[2]) for m in MIX]


def emit(rng, host, record_id, ts):
    eid, name = rng.choices(_E, weights=_W, k=1)[0]
    img = rng.choice(["C:\\Windows\\System32\\svchost.exe", "C:\\Program Files\\Contoso\\agent.exe",
                      "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"])
    d = (f"<Data Name='RuleName'>-</Data><Data Name='UtcTime'>{ts}</Data>"
         f"<Data Name='ProcessGuid'>{{a1b2c3d4-0000-0000-0000-{record_id:012d}}}</Data>"
         f"<Data Name='ProcessId'>{rng.randrange(400,9000)}</Data>"
         f"<Data Name='Image'>{img}</Data><Data Name='User'>CORP\\{rng.choice(environment.USERS)}</Data>")
    if eid == 3:
        d += (f"<Data Name='Protocol'>tcp</Data><Data Name='Initiated'>true</Data>"
              f"<Data Name='SourceIp'>{environment.ip_for(host)}</Data>"
              f"<Data Name='SourcePort'>{rng.randrange(1024,65535)}</Data>"
              f"<Data Name='DestinationIp'>{rng.choice(environment.EXTERNAL_HOSTS)}</Data>"
              f"<Data Name='DestinationPort'>{rng.choice([443,80,53])}</Data>")
    elif eid == 22:
        d += (f"<Data Name='QueryName'>{rng.choice(environment.DNS_COMMON + environment.DNS_RARE)}</Data>"
              f"<Data Name='QueryStatus'>0</Data><Data Name='QueryResults'>type: 5 ;</Data>")
    elif eid == 11:
        d += f"<Data Name='TargetFilename'>C:\\Users\\Public\\{record_id}.tmp</Data>"
    elif eid == 1:
        d += (f"<Data Name='CommandLine'>{img} -k netsvcs</Data>"
              f"<Data Name='ParentImage'>C:\\Windows\\System32\\services.exe</Data>"
              f"<Data Name='Hashes'>SHA256={record_id:064X}</Data>")
    raw = ('<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
           f'<System><Provider Name="Microsoft-Windows-Sysmon" '
           f'Guid="{{5770385f-c22a-43e0-bf4c-06f5698ffbd9}}"/><EventID>{eid}</EventID>'
           f'<Version>5</Version><Level>4</Level><Task>{eid}</Task>'
           f'<TimeCreated SystemTime="{ts}"/><EventRecordID>{record_id}</EventRecordID>'
           f'<Channel>Microsoft-Windows-Sysmon/Operational</Channel>'
           f'<Computer>{host}.{environment.DOMAIN}</Computer></System>'
           f'<EventData>{d}</EventData></Event>')
    return raw, {"eventid": eid, "name": name}
