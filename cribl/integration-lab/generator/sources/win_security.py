"""
Windows Security channel, weighted the way a real environment weights it.

The event set is chosen from what NIST SP 800-53r5 and CSF 2.0 actually need
evidence for, not from what is convenient to generate. CONTROLS below is the
map, and the lab asserts against it after reduction: a pipeline that saves
volume by removing a control's only evidence has not saved anything.
"""

import random
import environment

KEY = "win_security"
SOURCETYPE = "XmlWinEventLog:Security"
SOURCE = "WinEventLog:Security"
# Security-channel share of a 10k-endpoint environment's SIEM ingest.
SHARE = 17.0

# (weight, EventID, name). Weights approximate a Security channel with the
# audit policy a mature environment runs: connection noise dominates, and the events
# that matter for the control set are individually rare.
MIX = [
    (52, 5156, "Filtering Platform connection allowed"),
    (9,  5158, "Filtering Platform bind allowed"),
    (3,  5157, "Filtering Platform connection blocked"),
    (7,  4688, "Process creation"),
    (6,  4624, "Logon success"),
    (3,  4634, "Logoff"),
    (2,  4625, "Logon failure"),
    (2,  4672, "Special privileges assigned"),
    (2,  4768, "Kerberos TGT requested"),
    (2,  4769, "Kerberos service ticket requested"),
    (1,  4776, "NTLM credential validation"),
    (1,  4771, "Kerberos pre-authentication failed"),
    (1,  4648, "Logon with explicit credentials"),
    (1,  4657, "Registry value modified"),
    (1,  5136, "Directory object modified"),
    (1,  4673, "Privileged service called"),
    (1,  4703, "Token right adjusted"),
    (0.6, 4720, "User account created"),
    (0.6, 4726, "User account deleted"),
    (0.6, 4738, "User account changed"),
    (0.6, 4728, "Member added to global group"),
    (0.5, 4732, "Member added to local group"),
    (0.5, 4756, "Member added to universal group"),
    (0.5, 4740, "Account locked out"),
    (0.5, 4723, "Password change attempted"),
    (0.5, 4724, "Password reset attempted"),
    (0.4, 4722, "User account enabled"),
    (0.4, 4725, "User account disabled"),
    (0.4, 4778, "Session reconnected"),
    (0.4, 4779, "Session disconnected"),
    (0.3, 7045, "Service installed"),
    (0.3, 4697, "Service installed (Security)"),
    (0.3, 4719, "System audit policy changed"),
    (0.2, 4964, "Special group assigned to logon"),
    (0.2, 4698, "Scheduled task created"),
    (0.2, 4702, "Scheduled task updated"),
    (0.15, 1102, "Audit log cleared"),
    (0.15, 1100, "Event logging service shut down"),
    (0.3, 4704, "User right assigned"),
    (0.2, 4705, "User right removed"),
    (0.3, 4739, "Domain policy changed"),
    (0.4, 4798, "User's local group membership enumerated"),
    (0.3, 4799, "Security-enabled local group membership enumerated"),
    (0.8, 4656, "Handle to an object requested"),
    (0.3, 6416, "New external device recognized"),
    (0.2, 4732, "Member added to security-enabled local group"),
    (0.1, 4649, "Replay attack detected"),
]

# What each control needs, and which events evidence it. must_not_drop is the
# assertion the lab makes after reduction.
# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = "EventID"

CONTROLS = [
    ("AU-2",   "CSF DE.AE-03", [4719], True,  "audit events selected and their configuration protected"),
    ("AU-3",   "CSF DE.AE-03", [4688, 4624], True, "content of audit records"),
    ("AU-3(1)", "CSF DE.AE-03", [4688], True, "additional audit information, process command line"),
    ("AU-9",   "CSF PR.PS-04", [1102, 1100], True,  "audit information protected from modification"),
    ("AU-9(4)", "CSF PR.AA-05", [4704, 4705], True, "access to audit management restricted to a subset of privileged users"),
    ("AU-12",  "CSF DE.CM-01", [4688, 4624], True,  "audit record generation across components"),
    ("AC-2",   "CSF PR.AA-01", [4720, 4722, 4725, 4726, 4738, 4740], True, "account management"),
    ("AC-2(7)", "CSF PR.AA-05", [4728, 4732, 4756], True, "privileged account role membership"),
    ("AC-2(12)", "CSF DE.CM-01", [4798, 4799], True, "account monitoring for atypical use, group enumeration"),
    ("AC-3",   "CSF PR.AA-05", [4656], True, "access enforcement, object access attempts"),
    ("AC-6(9)", "CSF PR.AA-05", [4672, 4673, 4703], True, "auditing of privileged functions"),
    ("AC-7",   "CSF DE.CM-01", [4625, 4740, 4771], True, "unsuccessful logon attempts"),
    ("AC-17",  "CSF PR.AA-05", [4624, 4778, 4779], True, "remote access monitoring"),
    ("IA-2",   "CSF PR.AA-02", [4624, 4768, 4769, 4776], True, "identification and authentication"),
    ("IA-5",   "CSF PR.AA-01", [4723, 4724], True,  "authenticator management"),
    ("CM-3",   "CSF PR.PS-01", [4657, 5136, 4719, 4739], True, "configuration change control"),
    ("CM-8(3)", "CSF ID.AM-01", [6416], True, "component inventory, unauthorized component detection"),
    ("MP-2",   "CSF PR.DS-01", [6416], True, "media access, removable device recognition"),
    ("MP-7",   "CSF PR.DS-01", [6416], True, "media use restrictions"),
    ("CM-5",   "CSF PR.PS-01", [4657, 4697, 7045], True, "access restrictions for change"),
    ("CM-7",   "CSF PR.PS-02", [4688], True,  "least functionality, evidenced by process execution"),
    ("SI-4",   "CSF DE.CM-01", [4688, 4624, 5157], True, "system monitoring"),
    ("SI-7",   "CSF PR.DS-06", [4698, 4702, 7045], True, "software and information integrity"),
    ("SC-7",   "CSF PR.IR-01", [5157], True,  "boundary protection, host firewall denials"),
]

# The two events the pipeline drops. Named here so the lab can assert that the
# drop list and the control set do not intersect.
DROPPED_BY_DESIGN = [5156, 5158]

_WEIGHTS = [m[0] for m in MIX]
_IDS = [(m[1], m[2]) for m in MIX]


def _target(rng, host):
    if host in environment.DCS or host in environment.SERVERS:
        return rng.choice(environment.USERS + environment.ADMINS)
    return rng.choice(environment.USERS)


def emit(rng, host, record_id, ts):
    eid, name = rng.choices(_IDS, weights=_WEIGHTS, k=1)[0]
    user = _target(rng, host)
    ip = environment.ip_for(host)
    body = _body(rng, eid, host, user, ip)
    raw = (
        '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
        f'<System><Provider Name="Microsoft-Windows-Security-Auditing" '
        f'Guid="{{54849625-5478-4994-A5BA-3E3B0328C30D}}"/>'
        f'<EventID>{eid}</EventID><Version>0</Version><Level>0</Level>'
        f'<Task>{12544 + (eid % 64)}</Task><Opcode>0</Opcode>'
        f'<Keywords>0x8020000000000000</Keywords>'
        f'<TimeCreated SystemTime="{ts}"/><EventRecordID>{record_id}</EventRecordID>'
        f'<Correlation/><Execution ProcessID="4" ThreadID="{2000 + record_id % 900}"/>'
        f'<Channel>Security</Channel><Computer>{host}.{environment.DOMAIN}</Computer>'
        f'<Security/></System><EventData>{body}</EventData></Event>'
    )
    return raw, {"eventid": eid, "name": name, "user": user, "host": host}


def _d(name, value):
    return f"<Data Name='{name}'>{value}</Data>"


def _body(rng, eid, host, user, ip):
    dom = environment.DOMAIN.split(".")[0].upper()
    common = (_d("SubjectUserSid", "S-1-5-21-1085031214-1563985344-725345543-1103")
              + _d("SubjectUserName", user) + _d("SubjectDomainName", dom)
              + _d("SubjectLogonId", f"0x{rng.randrange(0x10000, 0xFFFFFF):x}"))
    if eid in (5156, 5157, 5158):
        return (common + _d("ProcessID", rng.randrange(400, 9000))
                + _d("Application", "\\device\\harddiskvolume2\\windows\\system32\\svchost.exe")
                + _d("Direction", rng.choice(["%%14592", "%%14593"]))
                + _d("SourceAddress", ip) + _d("SourcePort", rng.randrange(1024, 65535))
                + _d("DestAddress", rng.choice(environment.EXTERNAL_HOSTS + [environment.ip_for("DC-01")]))
                + _d("DestPort", rng.choice([443, 443, 443, 80, 53, 445, 3389]))
                + _d("Protocol", 6) + _d("FilterRTID", rng.randrange(60000, 90000))
                + _d("LayerName", "%%14610") + _d("LayerRTID", 44))
    if eid == 4688:
        img = rng.choice([
            "C:\\Windows\\System32\\cmd.exe", "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            "C:\\Program Files\\Contoso\\agent.exe", "C:\\Windows\\System32\\rundll32.exe"])
        cmd = img
        if "powershell" in img and rng.random() < 0.25:
            cmd = (img + " -NoProfile -NonInteractive -EncodedCommand "
                   "RwBlAHQALQBQAHIAbwBjAGUAcwBzACAALQBOAGEAbQBlACAAbABzAGEAcwBzACAAfAAgAE8AdQB0AC0ARgBpAGwAZQA=")
        return (common + _d("NewProcessId", f"0x{rng.randrange(0x100, 0xFFFF):x}")
                + _d("NewProcessName", img) + _d("TokenElevationType", "%%1936")
                + _d("ProcessId", "0x1f4") + _d("CommandLine", cmd)
                + _d("ParentProcessName", "C:\\Windows\\explorer.exe")
                + _d("MandatoryLabel", "S-1-16-8192"))
    if eid in (4624, 4634, 4648, 4778, 4779, 4964):
        return (common + _d("TargetUserName", user) + _d("TargetDomainName", dom)
                + _d("LogonType", rng.choice([2, 3, 3, 3, 10, 11]))
                + _d("WorkstationName", host) + _d("IpAddress", ip)
                + _d("IpPort", rng.randrange(1024, 65535))
                + _d("AuthenticationPackageName", rng.choice(["Kerberos", "NTLM", "Negotiate"]))
                + _d("LogonGuid", "{00000000-0000-0000-0000-000000000000}"))
    if eid in (4625, 4771, 4776, 4740):
        return (common + _d("TargetUserName", user) + _d("TargetDomainName", dom)
                + _d("Status", "0xc000006d") + _d("SubStatus", "0xc000006a")
                + _d("LogonType", 3) + _d("IpAddress", ip)
                + _d("WorkstationName", host) + _d("FailureReason", "%%2313"))
    if eid in (4768, 4769):
        return (common + _d("TargetUserName", f"{user}@{environment.DOMAIN}")
                + _d("ServiceName", rng.choice(["krbtgt", "cifs/dc-01", "HTTP/intranet"]))
                + _d("TicketOptions", "0x40810010") + _d("TicketEncryptionType", "0x12")
                + _d("IpAddress", f"::ffff:{ip}") + _d("Status", "0x0"))
    if eid in (4720, 4722, 4725, 4726, 4738, 4723, 4724):
        return (common + _d("TargetUserName", rng.choice(environment.USERS))
                + _d("TargetDomainName", dom) + _d("TargetSid", "S-1-5-21-1085031214-1563985344-725345543-2104")
                + _d("SamAccountName", rng.choice(environment.USERS))
                + _d("UserAccountControl", "%%2080 %%2082 %%2084"))
    if eid in (4728, 4732, 4756):
        return (common + _d("MemberName", f"CN={user},OU=Staff,DC=corp,DC=example")
                + _d("MemberSid", "S-1-5-21-1085031214-1563985344-725345543-2110")
                + _d("TargetUserName", rng.choice(["Domain Admins", "Server Operators", "Backup Operators"]))
                + _d("TargetDomainName", dom))
    if eid in (4672, 4673, 4703):
        return (common + _d("PrivilegeList",
                            "SeSecurityPrivilege\n\t\t\tSeBackupPrivilege\n\t\t\tSeRestorePrivilege\n\t\t\tSeTakeOwnershipPrivilege")
                + _d("Service", "Security"))
    if eid == 4657:
        return (common + _d("ObjectName", "\\REGISTRY\\MACHINE\\SYSTEM\\CurrentControlSet\\Services\\Contoso")
                + _d("ObjectValueName", "Start") + _d("OperationType", "%%1905")
                + _d("OldValue", "0x3") + _d("NewValue", "0x2")
                + _d("ProcessName", "C:\\Windows\\regedit.exe"))
    if eid == 5136:
        return (common + _d("DSName", environment.DOMAIN)
                + _d("ObjectDN", f"CN={user},OU=Staff,DC=corp,DC=example")
                + _d("ObjectClass", "user") + _d("AttributeLDAPDisplayName", "userAccountControl")
                + _d("AttributeValue", "512") + _d("OperationType", "%%14675"))
    if eid in (7045, 4697):
        return (common + _d("ServiceName", rng.choice(["ContosoAgent", "WinRing0", "UpdateSvc"]))
                + _d("ServiceFileName", "C:\\Windows\\Temp\\svc.exe")
                + _d("ServiceType", "0x10") + _d("ServiceStartType", "2")
                + _d("ServiceAccount", "LocalSystem"))
    if eid in (4698, 4702):
        return (common + _d("TaskName", "\\Contoso\\Updater")
                + _d("TaskContent", "&lt;?xml version=\"1.0\"?&gt;&lt;Task&gt;&lt;Actions&gt;&lt;Exec&gt;&lt;Command&gt;powershell.exe&lt;/Command&gt;&lt;/Exec&gt;&lt;/Actions&gt;&lt;/Task&gt;"))
    if eid == 4719:
        return (common + _d("CategoryId", "%%8280") + _d("SubcategoryId", "%%14080")
                + _d("SubcategoryGuid", "{0cce9215-69ae-11d9-bed3-505054503030}")
                + _d("AuditPolicyChanges", "%%8449"))
    if eid == 1102:
        return (_d("SubjectUserSid", "S-1-5-21-1085031214-1563985344-725345543-1103")
                + _d("SubjectUserName", user) + _d("SubjectDomainName", dom)
                + _d("SubjectLogonId", "0x3e7"))
    return common + _d("TargetUserName", user) + _d("TargetDomainName", dom)
