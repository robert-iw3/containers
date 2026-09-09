"""
Windows DNS Server Analytical channel, from the domain controllers.

Microsoft-Windows-DNS-Server/Analytical is ETW, and a forwarder renders it as
Windows XML - so a record is around a kilobyte, not the ~135 bytes of the
legacy debug log. That size, multiplied by every name every machine resolves,
is what makes DNS one of the two largest feeds in most environments and the single
best reduction target: the detections that read DNS read the rare names.
"""

import random
import environment

KEY = "win_dns"
SOURCETYPE = "XmlWinEventLog:Microsoft-Windows-DNS-Server/Analytical"
SOURCE = "WinEventLog:Microsoft-Windows-DNS-Server/Analytical"
SHARE = 16.0

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = "dns_event"

CONTROLS = [
    ("SI-4",   "CSF DE.CM-01", ["QUERY_RECEIVED", "RESPONSE_SUCCESS"], True, "monitoring for indicators via name resolution"),
    ("SI-4(4)", "CSF DE.CM-09", ["QUERY_RECEIVED"], True, "outbound communications monitoring"),
    ("SC-7",   "CSF PR.IR-01", ["RESPONSE_SUCCESS"], True, "boundary protection support"),
    ("AU-12",  "CSF DE.CM-01", ["QUERY_RECEIVED"], False, "audit generation; common names are aggregatable"),
]
DROPPED_BY_DESIGN = []

QTYPES = [(1, "A"), (1, "A"), (1, "A"), (28, "AAAA"), (12, "PTR"), (33, "SRV"), (16, "TXT"), (5, "CNAME")]


def emit(rng, host, record_id, ts):
    dc = host if host in environment.DCS else rng.choice(environment.DCS)
    client_host = rng.choice(environment.WORKSTATIONS + environment.SERVERS)
    client = environment.ip_for(client_host)
    rare = rng.random() < 0.03
    name = rng.choice(environment.DNS_RARE if rare else environment.DNS_COMMON)
    qt, qtname = rng.choice(QTYPES)
    xid = rng.randrange(0x1000, 0xFFFF)
    eid = 257 if rng.random() < 0.5 else 256      # RESPONSE_SUCCESS / QUERY_RECEIVED
    evname = "RESPONSE_SUCCESS" if eid == 257 else "QUERY_RECEIVED"
    packet = ("0x" + "".join(rng.choice("0123456789ABCDEF") for _ in range(rng.randrange(64, 160))))
    raw = ('<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
           '<System><Provider Name="Microsoft-Windows-DNSServer" '
           'Guid="{EB79061A-A566-4698-9119-3ED2807060E7}"/>'
           f'<EventID>{eid}</EventID><Version>0</Version><Level>4</Level>'
           f'<Task>{eid}</Task><Opcode>0</Opcode><Keywords>0x4000000000000000</Keywords>'
           f'<TimeCreated SystemTime="{ts}"/><EventRecordID>{record_id}</EventRecordID>'
           f'<Correlation/><Execution ProcessID="1928" ThreadID="{3000 + record_id % 900}"/>'
           f'<Channel>Microsoft-Windows-DNS-Server/Analytical</Channel>'
           f'<Computer>{dc}.{environment.DOMAIN}</Computer><Security UserID="S-1-5-18"/>'
           '</System><EventData>'
           f"<Data Name='TCP'>0</Data><Data Name='InterfaceIP'>{environment.ip_for(dc)}</Data>"
           f"<Data Name='Source'>{client}</Data><Data Name='RD'>1</Data>"
           f"<Data Name='QNAME'>{name}.</Data><Data Name='QTYPE'>{qt}</Data>"
           f"<Data Name='XID'>{xid}</Data><Data Name='DNSSEC'>0</Data>"
           f"<Data Name='Port'>{rng.randrange(49152, 65535)}</Data>"
           f"<Data Name='Flags'>{rng.choice(['256', '33152'])}</Data>"
           f"<Data Name='Scope'>Default</Data><Data Name='Zone'>{environment.DOMAIN}</Data>"
           f"<Data Name='PolicyName'>NULL</Data>"
           f"<Data Name='PacketData'>{packet}</Data>"
           f"<Data Name='ElapsedTime'>{rng.randrange(0, 4000)}</Data>"
           f"<Data Name='EventName'>{evname}</Data>"
           '</EventData></Event>')
    return raw, {"qname": name, "qtype": qtname, "rare": rare, "client": client, "dc": dc}
