"""
The non-Security Windows channels that carry control evidence.

Defender, Windows Update, Terminal Services, AppLocker, Code Integrity and the
System log. Individually small, and between them they are the only evidence for
a dozen 800-53r5 controls that the Security channel does not touch - which is
why an environment that collects only Security has a coverage gap it cannot see.
"""

import random
import environment

KEY = "win_system"
SOURCETYPE = "XmlWinEventLog:System"
SOURCE = "WinEventLog:System"
SHARE = 2.0

CONTROL_FIELD = "EventID"

CONTROLS = [
    ("IR-4",    "CSF RS.MA-01", [1116], True,  "incident handling, malware detected"),
    ("IR-4(1)", "CSF RS.MA-02", [1117], True,  "automated incident handling, action taken"),
    ("SI-3",    "CSF DE.CM-01", [1116, 1117], True, "malicious code protection"),
    ("MA-2",    "CSF ID.AM-08", [19], True,  "controlled maintenance, patch installation"),
    ("MA-4",    "CSF PR.AA-05", [21, 23, 24, 25], True, "nonlocal maintenance, remote desktop sessions"),
    ("CM-7",    "CSF PR.PS-02", [8003, 8004], True, "least functionality, application control"),
    ("CM-7(2)", "CSF PR.PS-02", [3077], True, "prevent program execution, code integrity"),
    ("CP-10",   "CSF RC.RP-01", [6005, 6008], True, "system recovery, unexpected shutdown"),
    ("SI-7",    "CSF PR.DS-06", [3077], True, "software and information integrity"),
]
DROPPED_BY_DESIGN = []

MIX = [
    (24, 6005, "Event log service started", "EventLog", "System"),
    (6,  6008, "Previous shutdown was unexpected", "EventLog", "System"),
    (20, 19,   "Update installed successfully", "Microsoft-Windows-WindowsUpdateClient", "System"),
    (14, 21,   "Remote Desktop session logon succeeded", "Microsoft-Windows-TerminalServices-LocalSessionManager", "Microsoft-Windows-TerminalServices-LocalSessionManager/Operational"),
    (7,  23,   "Remote Desktop session logoff", "Microsoft-Windows-TerminalServices-LocalSessionManager", "Microsoft-Windows-TerminalServices-LocalSessionManager/Operational"),
    (5,  24,   "Remote Desktop session disconnected", "Microsoft-Windows-TerminalServices-LocalSessionManager", "Microsoft-Windows-TerminalServices-LocalSessionManager/Operational"),
    (4,  25,   "Remote Desktop session reconnected", "Microsoft-Windows-TerminalServices-LocalSessionManager", "Microsoft-Windows-TerminalServices-LocalSessionManager/Operational"),
    (8,  1117, "Antimalware action taken", "Microsoft-Windows-Windows Defender", "Microsoft-Windows-Windows Defender/Operational"),
    (6,  1116, "Antimalware detected malware", "Microsoft-Windows-Windows Defender", "Microsoft-Windows-Windows Defender/Operational"),
    (4,  8003, "AppLocker would have blocked", "Microsoft-Windows-AppLocker", "Microsoft-Windows-AppLocker/EXE and DLL"),
    (2,  8004, "AppLocker blocked", "Microsoft-Windows-AppLocker", "Microsoft-Windows-AppLocker/EXE and DLL"),
    (2,  3077, "Code Integrity blocked an unsigned image", "Microsoft-Windows-CodeIntegrity", "Microsoft-Windows-CodeIntegrity/Operational"),
]
_W = [m[0] for m in MIX]
_E = [(m[1], m[2], m[3], m[4]) for m in MIX]

THREATS = ["Trojan:Win32/Emotet.RA!MTB", "HackTool:Win32/Mimikatz.D",
           "Behavior:Win32/Powemet.A!attk", "Ransom:Win32/Conti.A"]


def _d(n, v):
    return f"<Data Name='{n}'>{v}</Data>"


def emit(rng, host, record_id, ts):
    eid, name, provider, channel = rng.choices(_E, weights=_W, k=1)[0]
    user = rng.choice(environment.USERS)
    if eid in (1116, 1117):
        body = (_d("Product Name", "Microsoft Defender Antivirus")
                + _d("Threat Name", rng.choice(THREATS))
                + _d("Severity Name", rng.choice(["Severe", "High", "Moderate"]))
                + _d("Category Name", "Trojan")
                + _d("Path", f"file:_C:\\Users\\{user}\\Downloads\\invoice_{record_id}.exe")
                + _d("Detection User", f"CORP\\{user}")
                + _d("Action Name", "Quarantine" if eid == 1117 else "None"))
    elif eid == 19:
        body = (_d("updateTitle", f"2026-09 Cumulative Update for Windows 11 (KB50{record_id % 90000:05d})")
                + _d("updateGuid", f"{{{record_id:08x}-0000-0000-0000-000000000000}}")
                + _d("serviceGuid", "{9482F4B4-E343-43B6-B170-9A65BC822C77}"))
    elif eid in (21, 23, 24, 25):
        body = (_d("User", f"CORP\\{user}") + _d("SessionID", rng.randrange(2, 12))
                + _d("Address", rng.choice(environment.EXTERNAL_HOSTS + [environment.ip_for(host)])))
    elif eid in (8003, 8004):
        body = (_d("PolicyName", "EXE") + _d("RuleId", f"{{{record_id:08x}-0000-0000-0000-000000000000}}")
                + _d("RuleName", "Allow signed publishers")
                + _d("TargetUser", "S-1-5-21-1085031214-1563985344-725345543-2104")
                + _d("TargetProcessId", rng.randrange(400, 9000))
                + _d("FilePath", f"%OSDRIVE%\\USERS\\{user.upper()}\\DOWNLOADS\\TOOL{record_id}.EXE")
                + _d("FileHash", f"{record_id:064X}") + _d("Fqbn", "O=UNKNOWN"))
    elif eid == 3077:
        body = (_d("File Name", f"\\Device\\HarddiskVolume2\\Users\\{user}\\driver{record_id}.sys")
                + _d("Process Name", "\\Device\\HarddiskVolume2\\Windows\\System32\\services.exe")
                + _d("Requested Signing Level", "8") + _d("Validated Signing Level", "1")
                + _d("Status", "0xc0000428"))
    else:
        body = (_d("param1", "Windows") + _d("param2", "Event Log")
                + _d("Binary", f"{record_id:032X}"))
    raw = ('<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
           f'<System><Provider Name="{provider}"/><EventID>{eid}</EventID>'
           f'<Version>0</Version><Level>{rng.choice([2,3,4])}</Level><Task>0</Task>'
           f'<Opcode>0</Opcode><Keywords>0x8000000000000000</Keywords>'
           f'<TimeCreated SystemTime="{ts}"/><EventRecordID>{record_id}</EventRecordID>'
           f'<Correlation/><Execution ProcessID="{rng.randrange(400,9000)}" ThreadID="{rng.randrange(1000,9999)}"/>'
           f'<Channel>{channel}</Channel><Computer>{host}.{environment.DOMAIN}</Computer>'
           f'<Security UserID="S-1-5-18"/></System><EventData>{body}</EventData></Event>')
    return raw, {"eventid": eid, "name": name}
