"""
The environment: names, addresses and identities the sources share.

Every source draws its hosts, users and addresses from here, so a firewall log
and a Windows logon for the same session agree on who and where. A data set whose
sources contradict each other cannot be used to demonstrate correlation, which
is half of what a SIEM is for.
"""

WORKSTATIONS = [f"WKS-{i:04d}" for i in range(1, 26)]
SERVERS = [f"SRV-APP{i:02d}" for i in range(1, 6)] + [f"SRV-DB{i:02d}" for i in range(1, 3)]
DCS = ["DC-01", "DC-02"]
LINUX = [f"LNX-WEB{i:02d}" for i in range(1, 4)]

USERS = ["a.mercer", "j.okafor", "s.varga", "p.lindqvist", "r.castellanos",
         "t.nakamura", "m.oyelaran", "d.ferraro", "svc_backup", "svc_sql"]
ADMINS = ["adm.mercer", "adm.okafor"]

DOMAIN = "corp.example"
INTERNAL_CIDR = "10.20."
EXTERNAL_HOSTS = ["203.0.113.17", "198.51.100.42", "192.0.2.88", "203.0.113.201"]

# Names a workstation actually resolves, mixed with a handful an analyst cares
# about. The ratio matters: DNS volume is dominated by the boring ones.
DNS_COMMON = ["ctldl.windowsupdate.com", "settings-win.data.microsoft.com",
              "outlook.office365.com", "teams.microsoft.com", "corp.example",
              "dc-01.corp.example", "wpad.corp.example", "time.windows.com"]
DNS_RARE = ["cdn77-assets.b-cdn.net", "paste.ee", "api.telegram.org",
            "dynamic-dns-updates.duckdns.org"]


def ip_for(host):
    """Stable per-host address, so the same machine keeps one address."""
    h = sum(ord(c) for c in host)
    return f"{INTERNAL_CIDR}{(h // 254) % 200 + 10}.{h % 254 + 1}"


def mac_for(host):
    h = sum(ord(c) * (i + 7) for i, c in enumerate(host))
    return ":".join(f"{(h >> (8 * i)) & 0xFF:02X}" for i in range(6))
