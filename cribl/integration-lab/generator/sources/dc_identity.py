"""
The domain controller tier: Security channel, Directory Service, and DNS Analytical.

Three channels off the same machines, in one file because they share the seat map:
the Kerberos client address, the NTLM workstation name and the DNS source address
have to be the same machine for the same account, or the cross-source join this
data set exists to demonstrate has nothing to join on.

Record shapes follow what a forwarder renders with renderXml=1: Windows event XML
with single-quoted Data Name attributes, and for the Directory Service channel
positional Data elements with no Name at all - the difference that decides whether
an EventData extraction returns fields or nothing.
"""

import environment

KEY = "dc_security"
SOURCETYPE = "XmlWinEventLog:Security"
SOURCE = "WinEventLog:Security"
# The DC half of the Security-channel share. Registering this family means
# lowering win_security from 17.0 to 12.7 and removing win_dns, so the
# environment still sums to 100.
SHARE = 3.8

CONTROL_FIELD = "EventID"

CONTROLS = [
    ("IA-2",     "CSF PR.AA-02", [4768, 4769, 4776], True, "identification and authentication by the authoritative identity provider"),
    ("IA-2(1)",  "CSF PR.AA-03", [4768], True, "smart card authentication, witnessed by PreAuthType 16 and the certificate fields"),
    ("AC-7",     "CSF DE.CM-01", [4771, 4776], True, "unsuccessful logon attempts over the Kerberos and NTLM paths"),
    ("AC-6(9)",  "CSF PR.AA-05", [4662, 4672], True, "use of privileged functions: directory extended rights, and the rights held at logon"),
    ("SI-4(20)", "CSF DE.CM-01", [4662], True, "additional monitoring of privileged accounts against the identity store"),
    ("CM-5(1)",  "CSF PR.PS-01", [5136], True, "attributed directory change with the before and after value"),
    ("AC-2(4)",  "CSF PR.AA-01", [5136], True, "automated audit actions behind an account object change"),
    ("SI-4",     "CSF DE.CM-01", [4769], True, "domain-wide detection of credential attack against service accounts"),
    ("AU-3",     "CSF DE.AE-03", [4662, 5136], True, "content of audit records for the AD DS component"),
    ("AU-12",    "CSF DE.CM-01", [4768, 4769, 4624], True, "audit record generation on the domain controller"),
]
DROPPED_BY_DESIGN = []

# The DC Security channel is not only Kerberos: every LDAP, SMB and RPC bind to a
# DC writes 4624/4634, which is a third of the channel and is what makes the DC
# tier expensive. 4662 and 5136 exist only where a SACL grants the audit ACE; the
# weights below floor them so a 30,000-record lab run still carries a sample, and
# the production rate is in the volume estimate rather than here.
MIX = [(46, 4769), (17, 4624), (14, 4634), (7, 4672), (6, 4768),
       (4, 4776), (2.3, 4771), (2.0, 4662), (1.7, 5136)]
_W = [m[0] for m in MIX]
_E = [m[1] for m in MIX]

# Subcategory task ids, which are what an assessor reads to prove the right audit
# subcategory is on rather than a legacy category.
_TASK = {4768: 14339, 4771: 14339, 4769: 14337, 4776: 14336, 4662: 14080,
         5136: 14081, 4624: 12544, 4634: 12545, 4672: 12548}

_SID_BASE = "S-1-5-21-1085031214-1563985344-725345543"
_REALM = environment.DOMAIN.upper()
_NETBIOS = environment.DOMAIN.split(".")[0].upper()
_DN = ",".join(f"DC={p}" for p in environment.DOMAIN.split("."))

# Control access rights on the domain head. The first two together are DCSync.
_REPL_RIGHTS = ["{1131f6aa-9c07-11d1-f79f-00c04fc2dcd2}",
                "{1131f6ad-9c07-11d1-f79f-00c04fc2dcd2}",
                "{89e95b76-444d-4c62-991a-0facbeda640c}"]

# Kerberos pre-authentication failure codes. 0x6 is deliberately absent: an
# unknown principal never reaches pre-authentication and is logged as 4768.
_KRB_FAIL = [(62, "0x18"), (18, "0x12"), (12, "0x17"), (8, "0x25")]
_NTLM_STATUS = [(70, "0x0"), (16, "0xc000006a"), (7, "0xc0000064"),
                (4, "0xc0000234"), (3, "0xc0000072")]

_MULTIVALUED = ["servicePrincipalName", "member", "msDS-AllowedToDelegateTo"]
_SINGLE_VALUED = ["userAccountControl", "scriptPath", "msDS-SupportedEncryptionTypes",
                  "description", "sIDHistory"]

# Attribute syntax, which is part of the record and is not constant: a rule that
# matches on AttributeValue has to know whether it reads a string or an integer.
_SYNTAX = {"member": "2.5.5.1", "userAccountControl": "2.5.5.9",
           "msDS-SupportedEncryptionTypes": "2.5.5.9", "sIDHistory": "2.5.5.17"}

# One attribute change is a Value Deleted and a Value Added sharing one
# OpCorrelationID. The partner is held here and emitted on the very next record
# of this source, so the pair is adjacent in time the way AD writes it.
_PENDING_5136 = []

# Logon sessions in flight, so 4634 and 4672 carry a TargetLogonId that a 4624
# actually issued. Without it the logon lifecycle cannot be reconstructed.
_LOGON_IDS = {}
_LOGON_CAP = 64


def _seat(user):
    """The machine an account signs in from, derived from the shared host lists.

    Kerberos IpAddress, NTLM Workstation and the DNS query Source must agree for
    one account across three channels, so the seat is a pure function of the name
    rather than a fresh draw per record.
    """
    pool = environment.SERVERS if user.startswith("svc_") else environment.WORKSTATIONS
    return pool[sum(ord(c) for c in user) % len(pool)]


def _pick(rng, table):
    return rng.choices([t[1] for t in table], weights=[t[0] for t in table], k=1)[0]


def _stratified(table, n):
    """Deterministic selection by position in the run, not an independent draw.

    A feed this rare loses a whole event id to variance in a short run, and the
    lab asserts that every control still has evidence after reduction. The stride
    is coprime with the weight total, so the rare ids interleave instead of
    arriving in one block.
    """
    total = int(sum(t[0] for t in table))
    pos = (n * 37) % total
    acc = 0
    for weight, value in table:
        acc += weight
        if pos < acc:
            return value
    return table[-1][1]


def _d(name, value):
    return f"<Data Name='{name}'>{value}</Data>"


def _sid(n):
    return f"{_SID_BASE}-{n}"


def _guid(rng):
    hexd = "0123456789abcdef"
    parts = [8, 4, 4, 4, 12]
    return "{" + "-".join("".join(rng.choice(hexd) for _ in range(n)) for n in parts) + "}"


def _dc_of(rng, host):
    return host if host in environment.DCS else rng.choice(environment.DCS)


def _logon_id(rng, user, new=False):
    if new or user not in _LOGON_IDS:
        if len(_LOGON_IDS) >= _LOGON_CAP:
            _LOGON_IDS.pop(next(iter(_LOGON_IDS)))
        _LOGON_IDS[user] = f"0x{rng.randrange(0x100000, 0xFFFFFFF):x}"
    return _LOGON_IDS[user]


def _envelope(eid, dc, record_id, ts, body, failure=False):
    keywords = "0x8010000000000000" if failure else "0x8020000000000000"
    return ('<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
            '<System><Provider Name="Microsoft-Windows-Security-Auditing" '
            'Guid="{54849625-5478-4994-A5BA-3E3B0328C30D}"/>'
            f'<EventID>{eid}</EventID><Version>0</Version><Level>0</Level>'
            f'<Task>{_TASK[eid]}</Task><Opcode>0</Opcode><Keywords>{keywords}</Keywords>'
            f'<TimeCreated SystemTime="{ts}"/><EventRecordID>{record_id}</EventRecordID>'
            f'<Correlation/><Execution ProcessID="732" ThreadID="{4000 + record_id % 900}"/>'
            f'<Channel>Security</Channel><Computer>{dc}.{environment.DOMAIN}</Computer>'
            f'<Security/></System><EventData>{body}</EventData></Event>')


def _subject(rng, user):
    return (_d("SubjectUserSid", _sid(1103 + sum(ord(c) for c in user) % 40))
            + _d("SubjectUserName", user) + _d("SubjectDomainName", _NETBIOS)
            + _d("SubjectLogonId", _logon_id(rng, user)))


def _kerberos_as(rng, user, seat):
    """4768. Certificate fields populate only under PKINIT, so a password logon
    leaves them empty and an empty field is not a collection defect."""
    pkinit = user in environment.ADMINS or rng.random() < 0.12
    cert = ("" if not pkinit else
            _d("CertIssuerName", f"{_NETBIOS}-ISSUING-CA-01")
            + _d("CertSerialNumber", f"{rng.randrange(0x10**15, 0x10**16):032X}")
            + _d("CertThumbprint", f"{rng.randrange(0x10**23, 0x10**24):040X}"))
    if not cert:
        cert = _d("CertIssuerName", "") + _d("CertSerialNumber", "") + _d("CertThumbprint", "")
    return (_d("TargetUserName", user) + _d("TargetDomainName", _REALM)
            + _d("TargetSid", _sid(2100 + sum(ord(c) for c in user) % 60))
            + _d("ServiceName", "krbtgt") + _d("ServiceSid", _sid(502))
            + _d("TicketOptions", "0x40810010") + _d("Status", "0x0")
            + _d("TicketEncryptionType", "0x12")
            + _d("PreAuthType", "16" if pkinit else "2")
            + _d("IpAddress", f"::ffff:{environment.ip_for(seat)}")
            + _d("IpPort", rng.randrange(49152, 65535)) + cert), {"pkinit": pkinit}


def _kerberos_tgs(rng, user, seat):
    """4769. RC4 on a user-account SPN with TicketOptions 0x40810000 is the
    kerberoasting signature, which is why encryption type is not constant here."""
    roast = rng.random() < 0.02
    if roast:
        spn = rng.choice(["svc_sql", "svc_backup"])
        enc, opts = "0x17", "0x40810000"
    else:
        target = rng.choice(environment.SERVERS + environment.DCS)
        spn = rng.choice([f"{target}$", f"cifs/{target.lower()}.{environment.DOMAIN}",
                          f"HTTP/{target.lower()}.{environment.DOMAIN}",
                          f"LDAP/{target.lower()}.{environment.DOMAIN}"])
        enc, opts = "0x12", "0x40810000"
    return (_d("TargetUserName", f"{user}@{_REALM}") + _d("TargetDomainName", _REALM)
            + _d("ServiceName", spn) + _d("ServiceSid", _sid(1200 + rng.randrange(0, 40)))
            + _d("TicketOptions", opts) + _d("TicketEncryptionType", enc)
            + _d("IpAddress", f"::ffff:{environment.ip_for(seat)}")
            + _d("IpPort", rng.randrange(49152, 65535)) + _d("Status", "0x0")
            + _d("LogonGuid", "{00000000-0000-0000-0000-000000000000}")
            + _d("TransmittedServices", "-")), {"kerberoast": roast, "spn": spn}


def _kerberos_fail(rng, user, seat):
    """4771. Status is the pre-authentication failure code, not a logon status."""
    code = _pick(rng, _KRB_FAIL)
    return (_d("TargetUserName", user) + _d("TargetSid", _sid(2100 + rng.randrange(0, 60)))
            + _d("ServiceName", f"krbtgt/{_NETBIOS}")
            + _d("TicketOptions", "0x40810010") + _d("Status", code)
            + _d("PreAuthType", "2")
            + _d("IpAddress", f"::ffff:{environment.ip_for(seat)}")
            + _d("IpPort", rng.randrange(49152, 65535))
            + _d("CertIssuerName", "") + _d("CertSerialNumber", "")
            + _d("CertThumbprint", "")), {"failure_code": code}


def _ntlm(rng, user, seat):
    """4776. It carries a client-supplied NetBIOS workstation name and no address
    at all, and the name is routinely blank, which is why lockout attribution from
    this record alone fails."""
    blank = rng.random() < 0.18
    status = _pick(rng, _NTLM_STATUS)
    return (_d("PackageName", "MICROSOFT_AUTHENTICATION_PACKAGE_V1_0")
            + _d("TargetUserName", user)
            + _d("Workstation", "" if blank else seat)
            + _d("Status", status)), {"ntlm_status": status, "workstation_blank": blank}


def _logon(rng, user, seat):
    """4624 on a DC is a network logon for an LDAP, SMB or RPC bind, so the
    subject is null and the interesting identity is the target."""
    kerb = rng.random() < 0.82
    logon_id = _logon_id(rng, user, new=True)
    return (_d("SubjectUserSid", "S-1-0-0") + _d("SubjectUserName", "-")
            + _d("SubjectDomainName", "-") + _d("SubjectLogonId", "0x0")
            + _d("TargetUserSid", _sid(2100 + sum(ord(c) for c in user) % 60))
            + _d("TargetUserName", user) + _d("TargetDomainName", _NETBIOS)
            + _d("TargetLogonId", logon_id) + _d("LogonType", "3")
            + _d("LogonProcessName", "Kerberos" if kerb else "NtLmSsp ")
            + _d("AuthenticationPackageName", "Kerberos" if kerb else "NTLM")
            + _d("WorkstationName", "-" if kerb else seat)
            + _d("LogonGuid", "{00000000-0000-0000-0000-000000000000}")
            + _d("TransmittedServices", "-") + _d("LmPackageName", "-")
            + _d("KeyLength", "0") + _d("ProcessId", "0x0") + _d("ProcessName", "-")
            + _d("IpAddress", environment.ip_for(seat))
            + _d("IpPort", rng.randrange(49152, 65535))
            + _d("ImpersonationLevel", "%%1833") + _d("RestrictedAdminMode", "-")
            + _d("TargetOutboundUserName", "-") + _d("TargetOutboundDomainName", "-")
            + _d("VirtualAccount", "%%1843") + _d("TargetLinkedLogonId", "0x0")
            + _d("ElevatedToken", "%%1842")), {"logon_id": logon_id, "kerberos": kerb}


def _logoff(rng, user, seat):
    """4634. It carries the logon id and nothing about where the session came
    from, so it is only useful joined to the 4624 that opened it."""
    logon_id = _logon_id(rng, user)
    return (_d("TargetUserSid", _sid(2100 + sum(ord(c) for c in user) % 60))
            + _d("TargetUserName", user) + _d("TargetDomainName", _NETBIOS)
            + _d("TargetLogonId", logon_id) + _d("LogonType", "3")), {"logon_id": logon_id}


def _special_logon(rng, user, seat):
    """4672. The privilege list is multi-line with tab indentation exactly as
    Windows renders it, which is what exercises the harness's newline escaping."""
    privs = ["SeSecurityPrivilege", "SeBackupPrivilege", "SeRestorePrivilege",
             "SeTakeOwnershipPrivilege", "SeDebugPrivilege", "SeSystemEnvironmentPrivilege",
             "SeLoadDriverPrivilege", "SeImpersonatePrivilege", "SeEnableDelegationPrivilege"]
    keep = privs[:rng.randrange(4, len(privs) + 1)]
    return (_d("SubjectUserSid", _sid(2100 + sum(ord(c) for c in user) % 60))
            + _d("SubjectUserName", user) + _d("SubjectDomainName", _NETBIOS)
            + _d("SubjectLogonId", _logon_id(rng, user))
            + _d("PrivilegeList", "\n\t\t\t".join(keep))), {"privilege_count": len(keep)}


def _ds_access(rng, user, seat):
    """4662. The replication control access rights on the domain head are DCSync;
    everything else here is an ordinary audited write."""
    dcsync = rng.random() < 0.06
    if dcsync:
        props = "%%7688\n\t\t\t" + "\n\t\t\t".join(_REPL_RIGHTS)
        obj_name, obj_type, mask, access = _DN, "%{19195a5b-6da0-11d0-afd3-00c04fd930c9}", "0x100", "%%7688"
    else:
        props = "%%7685\n\t\t\t{bf967a86-0de6-11d0-a285-00aa003049e2}"
        obj_name = f"CN={user},OU=Staff,{_DN}"
        obj_type, mask, access = "%{bf967aba-0de6-11d0-a285-00aa003049e2}", "0x20", "%%7685"
    return (_subject(rng, user) + _d("ObjectServer", "DS") + _d("ObjectType", obj_type)
            + _d("ObjectName", obj_name) + _d("OperationType", "Object Access")
            + _d("HandleId", f"0x{rng.randrange(0x100, 0xFFFF):x}")
            + _d("AccessList", access) + _d("AccessMask", mask)
            + _d("Properties", props) + _d("AdditionalInfo", "-")
            + _d("AdditionalInfo2", "")), {"dcsync": dcsync, "object": obj_name}


def _ds_change(rng, user, seat):
    """5136. Replacing an attribute that already has a value is a Value Deleted
    and a Value Added sharing one OpCorrelationID, so a parser that counts records
    counts one change twice."""
    multivalued = rng.random() < 0.45
    attr = rng.choice(_MULTIVALUED if multivalued else _SINGLE_VALUED)
    target = rng.choice(environment.USERS)
    corr, obj_guid = _guid(rng), _guid(rng)
    obj_dn = f"CN={target},OU=Staff,{_DN}"
    old_value, new_value = _attr_values(rng, attr, target)

    def build(value, op):
        body = (_d("OpCorrelationID", corr) + _d("AppCorrelationID", "-")
                + _subject(rng, user) + _d("DSName", environment.DOMAIN)
                + _d("DSType", "%%14676") + _d("ObjectDN", obj_dn)
                + _d("ObjectGUID", obj_guid) + _d("ObjectClass", "user")
                + _d("AttributeLDAPDisplayName", attr)
                + _d("AttributeSyntaxOID", _SYNTAX.get(attr, "2.5.5.12"))
                + _d("AttributeValue", value) + _d("OperationType", op))
        return body, {"attribute": attr, "object": obj_dn, "correlation": corr}

    if multivalued or old_value != "-":
        _PENDING_5136.append(build(new_value, "%%14674"))
        return build(old_value, "%%14675")
    return build(new_value, "%%14674")


def _attr_values(rng, attr, target):
    if attr == "servicePrincipalName":
        host = rng.choice(environment.SERVERS).lower()
        return f"MSSQLSvc/{host}.{environment.DOMAIN}:1433", f"HTTP/{host}.{environment.DOMAIN}"
    if attr == "member":
        return (f"CN={rng.choice(environment.USERS)},OU=Staff,{_DN}",
                f"CN={rng.choice(environment.ADMINS)},OU=Admins,{_DN}")
    if attr == "msDS-AllowedToDelegateTo":
        return f"cifs/{rng.choice(environment.SERVERS).lower()}.{environment.DOMAIN}", \
               f"HOST/{rng.choice(environment.SERVERS).lower()}.{environment.DOMAIN}"
    if attr == "userAccountControl":
        return "0x200", rng.choice(["0x210", "0x80200", "0x1000200"])
    if attr == "msDS-SupportedEncryptionTypes":
        return "0x18", "0x1c"
    if attr == "sIDHistory":
        return "-", _sid(512)
    if attr == "scriptPath":
        return "logon.bat", f"\\\\{rng.choice(environment.SERVERS).lower()}\\netlogon\\run.vbs"
    return "-", f"updated by change record {target}"


def emit(rng, host, record_id, ts):
    # The paired-change queue and the logon table are per run, and a run restarts
    # the counter at 1.
    if record_id == 1:
        _PENDING_5136.clear()
        _LOGON_IDS.clear()
    dc = _dc_of(rng, host)
    if _PENDING_5136:
        body, extra = _PENDING_5136.pop(0)
        raw = _envelope(5136, dc, record_id, ts, body)
        meta = {"eventid": 5136, "dc": dc}
        meta.update(extra)
        return raw, meta
    eid = rng.choices(_E, weights=_W, k=1)[0]
    user = rng.choice(environment.USERS + environment.ADMINS)
    seat = _seat(user)
    if eid == 4768:
        body, extra = _kerberos_as(rng, user, seat)
    elif eid == 4769:
        body, extra = _kerberos_tgs(rng, user, seat)
    elif eid == 4771:
        body, extra = _kerberos_fail(rng, user, seat)
    elif eid == 4776:
        body, extra = _ntlm(rng, user, seat)
    elif eid == 4624:
        body, extra = _logon(rng, user, seat)
    elif eid == 4634:
        body, extra = _logoff(rng, user, seat)
    elif eid == 4672:
        body, extra = _special_logon(rng, user, seat)
    elif eid == 4662:
        body, extra = _ds_access(rng, user, seat)
    else:
        body, extra = _ds_change(rng, user, seat)
    raw = _envelope(eid, dc, record_id, ts, body, failure=(eid == 4771))
    meta = {"eventid": eid, "user": user, "seat": seat, "dc": dc,
            "client_ip": environment.ip_for(seat)}
    meta.update(extra)
    return raw, meta


class _SubSource:
    """A second channel off the same tier, exposing the module contract.

    The harness reads KEY, SOURCETYPE, SOURCE, SHARE, CONTROLS and emit() by
    attribute, so an instance registers in sources.ALL exactly like a module.
    These stay in this file because they share the seat map above.
    """

    def __init__(self, key, sourcetype, source, share, control_field, controls, emitter):
        self.KEY = key
        self.SOURCETYPE = sourcetype
        self.SOURCE = source
        self.SHARE = share
        self.CONTROL_FIELD = control_field
        self.CONTROLS = controls
        self.DROPPED_BY_DESIGN = []
        self.emit = emitter


# The ActiveDirectory_DomainService provider renders positional Data elements with
# no Name attribute and puts a Qualifiers attribute on EventID. Both break an
# EventData extraction written against the Security channel.
_DS_MIX = [(70, 2889), (18, 1644), (5, 3039), (4, 2887), (2, 1988), (1, 2042)]

_DIRSVC_CONTROLS = [
    ("SC-8",    "CSF PR.DS-02", [2889, 2887], True, "directory binds carried without signing or encryption, named per client"),
    ("SC-8(1)", "CSF PR.DS-02", [3039], True, "cryptographic protection of the directory channel, by exception"),
    ("SI-4",    "CSF DE.CM-01", [1644], True, "unindexed directory reads that enumerate the identity store"),
    ("CP-9",    "CSF PR.DS-11", [1988, 2042], True, "replication convergence across sites"),
]


def _dirsvc_emit(rng, host, record_id, ts):
    dc = _dc_of(rng, host)
    eid = _stratified(_DS_MIX, record_id)
    client_host = rng.choice(environment.SERVERS + environment.WORKSTATIONS)
    client = environment.ip_for(client_host)
    identity = rng.choice(environment.USERS)
    if eid == 2889:
        # Binding Type: 0 is a SASL bind without signing, 1 is a simple bind in
        # the clear, and the remediation differs by which.
        data = [f"{client}:{rng.randrange(49152, 65535)}",
                f"{_NETBIOS}\\{identity}", rng.choice(["0", "1"])]
    elif eid == 2887:
        data = [str(rng.randrange(1, 400)), str(rng.randrange(0, 90))]
    elif eid == 3039:
        data = [f"{client}:{rng.randrange(49152, 65535)}", f"{_NETBIOS}\\{identity}"]
    elif eid == 1644:
        # The LDAP filter is XML-escaped in the rendered record, so a rule that
        # unescapes before matching sees a different string than the raw.
        data = [client, _DN, "(&amp;(objectClass=user)(servicePrincipalName=*))", "2",
                str(rng.randrange(4000, 60000)), str(rng.randrange(1000, 90000)),
                str(rng.randrange(0, 40))]
    elif eid == 1988:
        data = [rng.choice(environment.DCS), _DN, _guid(rng)]
    else:
        data = [rng.choice(environment.DCS), _DN, str(rng.randrange(61, 400))]
    body = "".join(f"<Data>{v}</Data>" for v in data)
    level = 3 if eid in (2889, 3039, 1644) else 2
    raw = ('<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
           '<System><Provider Name="Microsoft-Windows-ActiveDirectory_DomainService" '
           'Guid="{0e8478c5-3605-4e8c-8497-1e730c959516}" EventSourceName="NTDS General"/>'
           f'<EventID Qualifiers="16384">{eid}</EventID><Version>0</Version>'
           f'<Level>{level}</Level><Task>{rng.choice([9, 14, 16])}</Task><Opcode>0</Opcode>'
           '<Keywords>0x8080000000000000</Keywords>'
           f'<TimeCreated SystemTime="{ts}"/><EventRecordID>{record_id}</EventRecordID>'
           '<Correlation/><Execution ProcessID="652" ThreadID="'
           f'{5000 + record_id % 900}"/><Channel>Directory Service</Channel>'
           f'<Computer>{dc}.{environment.DOMAIN}</Computer>'
           '<Security UserID="S-1-5-18"/></System>'
           f'<EventData>{body}</EventData></Event>')
    return raw, {"eventid": eid, "dc": dc, "client_ip": client, "identity": identity}


# SHARE is far above this channel's production share of bytes. A feed this small
# loses a whole event id to variance in a 30,000-record run, and the lab asserts
# that every control still has evidence after reduction.
dirsvc = _SubSource("dc_dirsvc", "XmlWinEventLog:Directory Service",
                    "WinEventLog:Directory Service", 0.5, "EventID",
                    _DIRSVC_CONTROLS, _dirsvc_emit)


# Analytical is an ETW trace, not a conventional log. The lab reproduces what an
# ETW consumer renders, which is the same event XML shape, so the parsing this
# proves is real; what it cannot reproduce is the silent record loss under load.
_DNS_MIX = [(42, 256, "QUERY_RECEIVED"), (38, 257, "RESPONSE_SUCCESS"),
            (7, 260, "RECURSE_QUERY_OUT"), (6, 261, "RECURSE_RESPONSE_IN"),
            (4, 258, "RESPONSE_FAILURE"), (2, 259, "IGNORED_QUERY"),
            (1, 262, "RECURSE_QUERY_TIMEOUT")]

_DNS_CONTROLS = [
    ("SI-4",     "CSF DE.CM-01", ["QUERY_RECEIVED", "RESPONSE_SUCCESS"], True, "detection of command and control and internal reconnaissance from the name service"),
    ("SI-4(4)",  "CSF DE.CM-09", ["RECURSE_QUERY_OUT", "RECURSE_RESPONSE_IN"], True, "inbound and outbound communications traffic for name resolution"),
    ("SI-4(18)", "CSF DE.CM-09", ["QUERY_RECEIVED"], True, "covert exfiltration in query name labels; the signal is the rare long QNAME"),
    ("AU-6(3)",  "CSF DE.AE-03", ["QUERY_RECEIVED"], True, "correlation of a source address to host and session records"),
]

_QTYPES = [(46, 1, "A"), (14, 28, "AAAA"), (12, 12, "PTR"), (14, 33, "SRV"),
           (6, 5, "CNAME"), (5, 16, "TXT"), (3, 15, "MX")]
_B32 = "abcdefghijklmnopqrstuvwxyz234567"
_FORWARDERS = ["10.20.9.53", "10.20.9.54"]


def _tunnel_qname(rng):
    """The exfiltration shape: a long encoded label under a rare parent. Query
    name length and label entropy are the detection, so a sampled DNS stream
    cannot carry SI-4(18) - the signal is in the records sampling drops."""
    labels = [("".join(rng.choice(_B32) for _ in range(rng.randrange(40, 63))))
              for _ in range(rng.randrange(1, 3))]
    return ".".join(labels) + "." + rng.choice(environment.DNS_RARE)


def _dns_emit(rng, host, record_id, ts):
    dc = _dc_of(rng, host)
    eid, evname = _pick(rng, [(w, (e, n)) for w, e, n in _DNS_MIX])
    user = rng.choice(environment.USERS)
    seat = _seat(user)
    client = environment.ip_for(seat)
    roll = rng.random()
    if roll < 0.004:
        name, qt, qtname, rare = _tunnel_qname(rng), 16, "TXT", True
    elif roll < 0.035:
        name, rare = rng.choice(environment.DNS_RARE), True
        qt, qtname = 1, "A"
    else:
        name, rare = rng.choice(environment.DNS_COMMON), False
        qt, qtname = _pick(rng, [(w, (t, n)) for w, t, n in _QTYPES])
    # Uppercase hex: the pipeline's PacketData mask matches 0x[0-9A-F]+, and a
    # lowercase rendering would pass through unreduced with nothing to show it.
    packet = "0x" + "".join(rng.choice("0123456789ABCDEF")
                            for _ in range(rng.randrange(64, 200)))
    common = (_d("TCP", "0") + _d("InterfaceIP", environment.ip_for(dc))
              + _d("RD", "1") + _d("QNAME", name + ".") + _d("QTYPE", qt)
              + _d("XID", rng.randrange(0x1000, 0xFFFF)))
    if eid in (256, 259):
        body = (common + _d("Source", client) + _d("Port", rng.randrange(49152, 65535))
                + _d("Flags", "256") + _d("DNSSEC", "0") + _d("Scope", "Default")
                + _d("Zone", environment.DOMAIN) + _d("PolicyName", "NULL")
                + _d("PacketData", packet))
    elif eid in (257, 258):
        body = (common + _d("Destination", client) + _d("Port", rng.randrange(49152, 65535))
                + _d("Flags", "33152") + _d("DNSSEC", "0")
                + _d("RCODE", "0" if eid == 257 else rng.choice(["2", "3", "5"]))
                + _d("Scope", "Default") + _d("Zone", environment.DOMAIN)
                + _d("PolicyName", "NULL") + _d("PacketData", packet)
                + _d("ElapsedTime", rng.randrange(0, 4000)))
    elif eid == 260:
        body = (common + _d("Destination", rng.choice(_FORWARDERS))
                + _d("Port", "53") + _d("Flags", "256") + _d("PacketData", packet))
    elif eid == 261:
        body = (common + _d("Source", rng.choice(_FORWARDERS))
                + _d("Port", "53") + _d("RCODE", "0")
                + _d("ElapsedTime", rng.randrange(4, 900)) + _d("PacketData", packet))
    else:
        body = common + _d("Destination", rng.choice(_FORWARDERS)) + _d("Port", "53")
    raw = ('<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
           '<System><Provider Name="Microsoft-Windows-DNSServer" '
           'Guid="{EB79061A-A566-4698-9119-3ED2807060E7}"/>'
           f'<EventID>{eid}</EventID><Version>0</Version><Level>4</Level>'
           f'<Task>{eid}</Task><Opcode>0</Opcode>'
           '<Keywords>0x4000000000000000</Keywords>'
           f'<TimeCreated SystemTime="{ts}"/><EventRecordID>{record_id}</EventRecordID>'
           f'<Correlation/><Execution ProcessID="1928" ThreadID="{3000 + record_id % 900}"/>'
           '<Channel>Microsoft-Windows-DNS-Server/Analytical</Channel>'
           f'<Computer>{dc}.{environment.DOMAIN}</Computer>'
           '<Security UserID="S-1-5-18"/></System>'
           f'<EventData>{body}{_d("EventName", evname)}</EventData></Event>')
    return raw, {"dns_event": evname, "eventid": eid, "qname": name, "qtype": qtname,
                 "rare": rare, "client_ip": client, "seat": seat, "user": user, "dc": dc}


dns_analytical = _SubSource("dc_dns_analytic",
                            "XmlWinEventLog:Microsoft-Windows-DNS-Server/Analytical",
                            "WinEventLog:Microsoft-Windows-DNS-Server/Analytical",
                            16.0, "dns_event", _DNS_CONTROLS, _dns_emit)

SUBSOURCES = [dirsvc, dns_analytical]
