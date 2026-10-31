"""
Cisco ASA, IOS routers and switches, and ISE.

Three feeds in one module because they are one collection tier: one syslog
receiver, one forwarder, one set of correlation keys. Each feed object
satisfies the module contract (KEY, SOURCETYPE, SOURCE, SHARE, emit), so
sources/__init__.py imports the objects rather than the module.

Wire formats assume the device configuration the onboarding guide sets: UTC
clocks, `logging timestamp` on the ASA, `service timestamps log datetime msec
show-timezone year` on IOS, device-id and origin-id on, and the ISE remote
logging target raised to 8192 bytes so no record is segmented.
"""

import random
from datetime import datetime

import environment

# Syslog facility per product: ASA defaults to local4, IOS to local7, and the
# ISE remote logging target to local6. PRI is computed from the mnemonic's own
# severity so the header and the message can never disagree.
_FACILITY = {"asa": 20, "ios": 23, "ise": 22}

ASA_DEVICES = ["asa-perim-01", "asa-perim-02"]
ROUTERS = ["rtr-core-01", "rtr-wan-01"]
SWITCHES = [f"sw-acc-{i:02d}" for i in range(1, 9)] + ["sw-dist-01", "sw-dist-02"]
ISE_NODES = ["ise-psn-01", "ise-psn-02"]

# Avoids 198.51.100.42, which environment.EXTERNAL_HOSTS already uses as a peer.
NAT_POOL = [f"198.51.100.{n}" for n in range(1, 9)]
VPN_POOL_PREFIX = "10.99."

DACL = "xACSACLx-IP-CORP_ACCESS-5f2a1b3c"
QUARANTINE_DACL = "xACSACLx-IP-QUARANTINE-9c40ee71"


def _pri(product, severity):
    return f"<{_FACILITY[product] * 8 + severity}>"


def _when(ts):
    """Tolerated parse failure keeps a driver timestamp change from killing the feed."""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return datetime(2026, 1, 1)


def _asa_ts(w):
    return w.strftime("%b %d %Y %H:%M:%S") + " UTC"


def _ios_ts(w, authoritative=True):
    """A leading asterisk is IOS saying the clock is not NTP-synchronized.

    The marker sits ahead of the month, so TIME_PREFIX has to tolerate it or
    every record from an unsynchronized device fails to parse.
    """
    mark = "" if authoritative else "*"
    return (f"{mark}{w.strftime('%b')} {w.day:>2d} {w.year} "
            f"{w.strftime('%H:%M:%S')}.{w.microsecond // 1000:03d} UTC")


def _ios_clock(w):
    return w.strftime("%H:%M:%S UTC %a %b %d %Y")


def _ise_header_ts(w):
    return f"{w.strftime('%b')} {w.day:>2d} {w.strftime('%H:%M:%S')}"


def _ise_body_ts(w):
    return w.strftime("%Y-%m-%d %H:%M:%S.") + f"{w.microsecond // 1000:03d} +00:00"


def _ios_mac(mac):
    """IOS writes dotted-triple lowercase where ISE writes dash-separated upper."""
    flat = mac.replace(":", "").lower()
    return f"{flat[0:4]}.{flat[4:8]}.{flat[8:12]}"


def _ise_mac(mac):
    return mac.replace(":", "-").upper()


def _switch_for(endpoint):
    """Switch, port and session id are functions of the endpoint in both feeds.

    The switch record and the ISE record must agree on AuditSessionID or the
    join this data set exists to demonstrate does not resolve.
    """
    h = sum(ord(c) * (i + 3) for i, c in enumerate(endpoint))
    return SWITCHES[h % len(SWITCHES)], (h % 46) + 1


def _audit_session(nas_ip, mac, w):
    ip_hex = "".join(f"{int(o):02X}" for o in nas_ip.split("."))
    n = (sum(ord(c) for c in mac) * 2654435761) & 0xFFFFFF
    stamp = (w.timetuple().tm_yday * 24 + w.hour) & 0xFFFFFFFF
    return f"{ip_hex}{n:08X}{stamp:08X}"


def _vpn_addr(user):
    h = sum(ord(c) for c in user)
    return f"{VPN_POOL_PREFIX}{h % 16 + 1}.{h % 200 + 20}"


def _pick(rng, table):
    total = sum(w for w, _ in table)
    roll = rng.random() * total
    for weight, name in table:
        roll -= weight
        if roll <= 0:
            return name
    return table[-1][1]


class Asa:
    """ASA perimeter and VPN head-end syslog.

    The connection and translation classes are the bulk. Build and teardown are
    paired on connection id by deriving the five-tuple from the id, so a flow
    can actually be reconstructed from the data set.
    """

    KEY = "cisco_asa"
    SOURCETYPE = "cisco:asa"
    SOURCE = "/var/log/network/cisco_asa/asa-perim-01/asa-perim-01.log"
    SHARE = 8.0
    CONTROL_FIELD = "asa_id"

    CONTROLS = [
        ("SC-7",     "CSF PR.IR-01", ["302013", "302014"], True,  "monitor and control at the managed interface"),
        ("SC-7(5)",  "CSF PR.IR-01", ["106023"], True,  "deny by default, observed in operation"),
        ("SI-4(4)",  "CSF DE.CM-01", ["302013", "302014"], True,  "inbound and outbound traffic record"),
        ("SI-4(11)", "CSF DE.CM-09", ["302014"], True,  "byte counts for outbound volume anomaly analysis"),
        ("AC-17(1)", "CSF PR.AA-05", ["113039", "722051", "113019"], True, "remote access monitored and controlled"),
        ("SC-10",    "CSF PR.AA-05", ["113019"], True,  "teardown reason carries idle-timeout enforcement"),
        ("IA-2",     "CSF PR.AA-02", ["113004", "113005"], True,  "unique identification before the tunnel is built"),
        ("IA-2(1)",  "CSF PR.AA-03", ["113012", "113015"], True,  "local-database fallback, where MFA is not applied"),
        ("AC-6(9)",  "CSF PR.AA-05", ["111008", "502103"], True,  "privileged function and privilege change"),
        ("MA-4(1)",  "CSF PR.AA-05", ["605005", "611101"], True,  "nonlocal maintenance session on the device"),
    ]
    # Nothing. The tempting cut is the 302xxx class, and cutting it removes the
    # permit record that SC-7 and SI-4(4) rest on.
    DROPPED_BY_DESIGN = []

    SHAPES = [
        (46.0, "conn_tcp"), (12.0, "conn_udp"), (14.0, "xlate"),
        (16.0, "deny"), (3.0, "acl_hit"), (2.5, "aaa"),
        (2.5, "vpn"), (2.0, "mgmt"), (2.0, "pki"),
    ]

    def emit(self, rng, host, record_id, ts):
        w = _when(ts)
        stamp = _asa_ts(w)
        dev = host if host in ASA_DEVICES else rng.choice(ASA_DEVICES)

        # Both halves of a pair draw the same shape and the same five-tuple, so
        # every teardown belongs to a build that is actually in the data set.
        pair = record_id // 2
        prng = random.Random(pair ^ 0x5A5A5A)
        shape = _pick(prng, self.SHAPES)
        closing = bool(record_id % 2)
        cid = 10_000_000 + pair

        if shape in ("conn_tcp", "conn_udp", "xlate"):
            proto = "UDP" if shape == "conn_udp" else "TCP"
            inside_host = prng.choice(environment.WORKSTATIONS + environment.SERVERS)
            real = environment.ip_for(inside_host)
            mapped = prng.choice(NAT_POOL)
            peer = prng.choice(environment.EXTERNAL_HOSTS)
            sport = prng.randrange(1024, 65535)
            dport = prng.choice([443, 443, 443, 80, 53, 123, 389]) if proto == "TCP" else prng.choice([53, 123, 443])
            if shape == "xlate":
                if closing:
                    raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-305012: Teardown dynamic {proto} "
                           f"translation from inside:{real}/{sport} to outside:{mapped}/{sport} "
                           f"duration {prng.randrange(0, 3)}:{prng.randrange(0, 59):02d}:{prng.randrange(0, 59):02d}")
                    kind = "xlate_teardown"
                else:
                    raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-305011: Built dynamic {proto} "
                           f"translation from inside:{real}/{sport} to outside:{mapped}/{sport}")
                    kind = "xlate_built"
                asa_id = "305012" if closing else "305011"
            else:
                # Direction is the initiator; the first pair is always the
                # lower-security interface, so "for" is not the source on an
                # outbound connection and a parser that assumes it inverts src
                # and dest on most of the feed.
                built, torn = ("302013", "302014") if proto == "TCP" else ("302015", "302016")
                if closing:
                    dur = f"{prng.randrange(0, 4)}:{prng.randrange(0, 59):02d}:{prng.randrange(0, 59):02d}"
                    # Only the TCP teardown carries a reason; 302016 ends at the byte count.
                    reason = (" " + prng.choice(["TCP FINs", "TCP Reset-I", "TCP Reset-O", "SYN Timeout"])
                              ) if proto == "TCP" else ""
                    raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-{torn}: Teardown {proto} connection {cid} "
                           f"for outside:{peer}/{dport} to inside:{real}/{sport} duration {dur} "
                           f"bytes {prng.randrange(120, 4_000_000)}{reason}")
                    asa_id = torn
                    kind = "teardown"
                else:
                    raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-{built}: Built outbound {proto} connection {cid} "
                           f"for outside:{peer}/{dport} ({peer}/{dport}) "
                           f"to inside:{real}/{sport} ({mapped}/{sport})")
                    asa_id = built
                    kind = "built"
            return raw, {"kind": kind, "asa_id": asa_id, "device": dev,
                         "src": real, "dest": peer, "conn_id": cid}

        if shape == "deny":
            peer = rng.choice(environment.EXTERNAL_HOSTS)
            target = environment.ip_for(rng.choice(environment.SERVERS))
            raw = (f"{_pri('asa', 4)}{stamp}: {dev} : %ASA-4-106023: Deny tcp "
                   f"src outside:{peer}/{rng.randrange(1024, 65535)} "
                   f"dst dmz:{target}/{rng.choice([445, 3389, 22, 1433, 23])} "
                   f"by access-group \"outside_access_in\" [0x0, 0x0]")
            return raw, {"kind": "deny", "asa_id": "106023", "device": dev,
                         "src": peer, "dest": target}

        if shape == "acl_hit":
            # The `log` keyword replaces 106023 with an interval-summarized
            # 106100 whose hit-cnt is the event count; counting records
            # undercounts by the summarization factor.
            peer = rng.choice(environment.EXTERNAL_HOSTS)
            target = environment.ip_for(rng.choice(environment.SERVERS))
            verdict = "denied" if rng.random() < 0.7 else "permitted"
            raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-106100: access-list outside_access_in "
                   f"{verdict} tcp outside/{peer}({rng.randrange(1024, 65535)}) -> "
                   f"dmz/{target}({rng.choice([443, 445, 3389])}) "
                   f"hit-cnt {rng.randrange(1, 400)} 300-second interval [0x0, 0x0]")
            return raw, {"kind": "acl_hit", "asa_id": "106100", "device": dev,
                         "src": peer, "dest": target}

        if shape == "aaa":
            user = rng.choice(environment.USERS)
            server = environment.ip_for(rng.choice(ISE_NODES))
            peer = rng.choice(environment.EXTERNAL_HOSTS)
            roll = rng.random()
            if roll < 0.72:
                raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-113004: AAA user authentication "
                       f"Successful : server = {server} : user = {user}")
                asa_id, kind = "113004", "aaa_ok"
            elif roll < 0.95:
                raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-113005: AAA user authentication "
                       f"Rejected : reason = AAA failure : server = {server} : user = {user} : "
                       f"user IP = {peer}")
                asa_id, kind = "113005", "aaa_reject"
            else:
                # Local fallback is the only record that the central identity
                # store, and every control it enforces, was bypassed.
                raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-113012: AAA user authentication "
                       f"Successful : local database : user = {user}")
                asa_id, kind = "113012", "aaa_local"
            return raw, {"kind": kind, "asa_id": asa_id, "device": dev, "user": user}

        if shape == "vpn":
            user = rng.choice(environment.USERS)
            peer = rng.choice(environment.EXTERNAL_HOSTS)
            assigned = _vpn_addr(user)
            roll = rng.random()
            if roll < 0.34:
                raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-113039: Group <CorpVPN> User <{user}> "
                       f"IP <{peer}> AnyConnect parent session started.")
                asa_id, kind = "113039", "vpn_start"
            elif roll < 0.67:
                raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-722051: Group <CorpVPN> User <{user}> "
                       f"IP <{peer}> IPv4 Address <{assigned}> IPv6 address <::> assigned to session")
                asa_id, kind = "722051", "vpn_assign"
            else:
                reason = rng.choice(["User Requested", "Idle Timeout", "Max time exceeded",
                                     "Lost Service", "Administrator Reset"])
                raw = (f"{_pri('asa', 4)}{stamp}: {dev} : %ASA-4-113019: Group = CorpVPN, "
                       f"Username = {user}, IP = {peer}, Session disconnected. Session Type: SSL, "
                       f"Duration: {rng.randrange(0, 9)}h:{rng.randrange(0, 59):02d}m:{rng.randrange(0, 59):02d}s, "
                       f"Bytes xmt: {rng.randrange(10**4, 10**8)}, Bytes rcv: {rng.randrange(10**4, 10**8)}, "
                       f"Reason: {reason}")
                asa_id, kind = "113019", "vpn_end"
            return raw, {"kind": kind, "asa_id": asa_id, "device": dev,
                         "user": user, "vpn_addr": assigned}

        if shape == "pki":
            user = rng.choice(environment.USERS)
            raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-717022: Certificate was successfully "
                   f"validated. serial number: {rng.randrange(16**8, 16**9):09X}, "
                   f"subject name: cn={user},ou=PKI,ou=DoD,o=U.S. Government,c=US.")
            return raw, {"kind": "pki_ok", "asa_id": "717022", "device": dev, "user": user}

        admin = rng.choice(environment.ADMINS)
        src = environment.ip_for(rng.choice(environment.WORKSTATIONS))
        roll = rng.random()
        if roll < 0.4:
            raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-605005: Login permitted from "
                   f"{src}/{rng.randrange(1024, 65535)} to management:{environment.ip_for(dev)}/ssh "
                   f"for user \"{admin}\"")
            asa_id, kind = "605005", "mgmt_login"
        elif roll < 0.55:
            raw = (f"{_pri('asa', 6)}{stamp}: {dev} : %ASA-6-605004: Login denied from "
                   f"{src}/{rng.randrange(1024, 65535)} to management:{environment.ip_for(dev)}/ssh "
                   f"for user \"{admin}\"")
            asa_id, kind = "605004", "mgmt_denied"
        elif roll < 0.7:
            raw = (f"{_pri('asa', 5)}{stamp}: {dev} : %ASA-5-502103: User priv level changed: "
                   f"Uname: {admin} From: 1 To: 15")
            asa_id, kind = "502103", "priv_change"
        else:
            # 111008 covers configuration-affecting commands only; every show
            # command is absent unless TACACS+ command accounting is on.
            cmd = rng.choice([
                "access-list outside_access_in extended permit tcp any host 10.30.1.20 eq 443",
                "no access-list outside_access_in line 14",
                "logging trap notifications",
                "username svc_monitor password ***** privilege 5",
                "write memory"])
            raw = (f"{_pri('asa', 5)}{stamp}: {dev} : %ASA-5-111008: User '{admin}' executed the "
                   f"'{cmd}' command.")
            asa_id, kind = "111008", "config_cmd"
        return raw, {"kind": kind, "asa_id": asa_id, "device": dev, "user": admin}


class Ios:
    """IOS and IOS-XE router and switch syslog.

    Port access is most of the volume and is driven by the reauthentication
    timer, not by people. Interface names and MAC notation are inconsistent
    between mnemonic families on purpose: that is what the wire carries.
    """

    KEY = "cisco_ios"
    SOURCETYPE = "cisco:ios"
    SOURCE = "/var/log/network/cisco_ios/sw-acc-01/sw-acc-01.log"
    SHARE = 1.5
    CONTROL_FIELD = "ios_mnemonic"

    CONTROLS = [
        ("CM-5(1)", "CSF PR.PS-01", ["SYS-5-CONFIG_I", "PARSER-5-CFGLOG_LOGGEDCMD"], True,
         "automatic audit record for every configuration change action"),
        ("AC-7",    "CSF PR.AA-01", ["SEC_LOGIN-4-LOGIN_FAILED", "SEC_LOGIN-1-QUIET_MODE_ON"], True,
         "the failure sequence and the lockout that fired"),
        ("IA-2",    "CSF PR.AA-02", ["SEC_LOGIN-5-LOGIN_SUCCESS"], True,
         "administrative session resolves to an individual"),
        ("MA-4(1)", "CSF PR.AA-05", ["SEC_LOGIN-5-LOGIN_SUCCESS", "SYS-6-LOGOUT"], True,
         "nonlocal maintenance logged at start and exit"),
        ("AC-6(9)", "CSF PR.AA-05", ["SYS-5-PRIV_AUTH_PASS"], True, "escalation to privilege level 15"),
        ("IA-3",    "CSF PR.AA-01", ["AUTHMGR-5-SUCCESS", "DOT1X-5-FAIL"], True,
         "port stays unauthorized until authentication completes"),
        ("AC-3",    "CSF PR.AA-05", ["EPM-6-POLICY_APP_SUCCESS", "EPM-6-POLICY_APP_FAILURE"], True,
         "the authorization ISE computed was actually installed at the port"),
        ("CM-8(3)", "CSF ID.AM-01", ["PORT_SECURITY-2-PSECURE_VIOLATION"], True,
         "unauthorized hardware attaching to an access port"),
        ("AU-8",    "CSF PR.PS-04", ["SYS-6-CLOCKUPDATE"], True, "a named individual changed the clock"),
    ]
    # LINEPROTO repeats what LINK already said about the same port within a
    # second, and the catalog makes link state correlation-only evidence.
    DROPPED_BY_DESIGN = ["LINEPROTO-5-UPDOWN"]

    SHAPES = [
        (40.0, "dot1x"), (16.0, "epm"), (22.0, "link"), (6.0, "login"),
        (5.0, "config"), (4.0, "portsec"), (4.0, "l2"), (3.0, "infra"),
    ]

    def emit(self, rng, host, record_id, ts):
        w = _when(ts)
        # A small share of records come from a device that lost NTP, so the lab
        # can prove both the parser and the AU-8 detection handle it.
        authoritative = rng.random() > 0.015
        stamp = _ios_ts(w, authoritative)
        seq = record_id % 1_000_000
        shape = _pick(rng, self.SHAPES)

        endpoint = rng.choice(environment.WORKSTATIONS)
        dev, port = _switch_for(endpoint)
        nas_ip = environment.ip_for(dev)
        mac = environment.mac_for(endpoint)
        short_if, long_if = f"Gi1/0/{port}", f"GigabitEthernet1/0/{port}"
        asid = _audit_session(nas_ip, mac, w)

        def line(sev, body):
            return f"{_pri('ios', sev)}{dev}: {seq:06d}: {stamp}: {body}"

        if shape == "dot1x":
            roll = rng.random()
            if roll < 0.42:
                raw = line(5, f"%AUTHMGR-5-START: Starting 'dot1x' for client ({_ios_mac(mac)}) "
                              f"on Interface {short_if} AuditSessionID {asid}")
                mnem = "AUTHMGR-5-START"
            elif roll < 0.92:
                raw = line(5, f"%AUTHMGR-5-SUCCESS: Authorization succeeded for client ({_ios_mac(mac)}) "
                              f"on Interface {short_if} AuditSessionID {asid}")
                mnem = "AUTHMGR-5-SUCCESS"
            elif roll < 0.97:
                raw = line(5, f"%DOT1X-5-FAIL: Authentication failed for client ({_ios_mac(mac)}) "
                              f"on Interface {short_if} AuditSessionID {asid}")
                mnem = "DOT1X-5-FAIL"
            else:
                raw = line(5, f"%AUTHMGR-5-FAIL: Authorization failed or unapplied for client "
                              f"({_ios_mac(mac)}) on Interface {short_if} AuditSessionID {asid}")
                mnem = "AUTHMGR-5-FAIL"
            return raw, {"kind": "dot1x", "ios_mnemonic": mnem, "device": dev,
                         "mac": mac, "audit_session_id": asid, "port": short_if}

        if shape == "epm":
            roll = rng.random()
            if roll < 0.55:
                raw = line(6, f"%EPM-6-POLICY_APP_SUCCESS: Policy Application succeeded, "
                              f"Client MAC {_ios_mac(mac)}, AuditSessionID {asid}, Policy Type: ACL, "
                              f"Policy Name: {DACL}")
                mnem = "EPM-6-POLICY_APP_SUCCESS"
            elif roll < 0.94:
                # Pipe-delimited with a trailing pipe per field, unlike every
                # other EPM message.
                raw = line(6, f"%EPM-6-IPEVENT: IP={environment.ip_for(endpoint)}| MAC={_ios_mac(mac)}| "
                              f"AUDITSESID={asid}| AUTHTYPE=DOT1X| EVENT=IP-ASSIGNMENT")
                mnem = "EPM-6-IPEVENT"
            else:
                # ISE shows Access-Accept with a dACL, the switch failed to
                # install it, and the port forwards unrestricted.
                raw = line(6, f"%EPM-6-POLICY_APP_FAILURE: Policy Application failed, "
                              f"Client MAC {_ios_mac(mac)}, AuditSessionID {asid}, Policy Type: ACL, "
                              f"Policy Name: {DACL}, Failure Reason: ACL download failed")
                mnem = "EPM-6-POLICY_APP_FAILURE"
            return raw, {"kind": "epm", "ios_mnemonic": mnem, "device": dev,
                         "mac": mac, "audit_session_id": asid, "src": environment.ip_for(endpoint)}

        if shape == "link":
            state = "up" if rng.random() < 0.5 else "down"
            if rng.random() < 0.5:
                raw = line(3, f"%LINK-3-UPDOWN: Interface {long_if}, changed state to {state}")
                mnem = "LINK-3-UPDOWN"
            else:
                raw = line(5, f"%LINEPROTO-5-UPDOWN: Line protocol on Interface {long_if}, "
                              f"changed state to {state}")
                mnem = "LINEPROTO-5-UPDOWN"
            return raw, {"kind": "link", "ios_mnemonic": mnem, "device": dev, "port": long_if}

        if shape == "login":
            admin = rng.choice(environment.ADMINS)
            src = environment.ip_for(rng.choice(environment.WORKSTATIONS))
            roll = rng.random()
            if roll < 0.5:
                raw = line(5, f"%SEC_LOGIN-5-LOGIN_SUCCESS: Login Success [user: {admin}] "
                              f"[Source: {src}] [localport: 22] at {_ios_clock(w)}")
                mnem = "SEC_LOGIN-5-LOGIN_SUCCESS"
            elif roll < 0.72:
                raw = line(4, f"%SEC_LOGIN-4-LOGIN_FAILED: Login failed [user: {admin}] "
                              f"[Source: {src}] [localport: 22] [Reason: Login Authentication Failed] "
                              f"at {_ios_clock(w)}")
                mnem = "SEC_LOGIN-4-LOGIN_FAILED"
            elif roll < 0.80:
                raw = line(1, f"%SEC_LOGIN-1-QUIET_MODE_ON: Still timeleft for watching failures is "
                              f"{rng.randrange(20, 110)} secs, [user: {admin}] [Source: {src}] "
                              f"[localport: 22] [Reason: Login Authentication Failed]")
                mnem = "SEC_LOGIN-1-QUIET_MODE_ON"
            elif roll < 0.92:
                raw = line(5, f"%SYS-5-PRIV_AUTH_PASS: Privilege level set to 15 by {admin} on vty0")
                mnem = "SYS-5-PRIV_AUTH_PASS"
            else:
                raw = line(6, f"%SYS-6-LOGOUT: User {admin} has exited tty session "
                              f"{rng.randrange(1, 6)}({src})")
                mnem = "SYS-6-LOGOUT"
            return raw, {"kind": "login", "ios_mnemonic": mnem, "device": dev,
                         "user": admin, "src": src}

        if shape == "config":
            admin = rng.choice(environment.ADMINS)
            src = environment.ip_for(rng.choice(environment.WORKSTATIONS))
            roll = rng.random()
            if roll < 0.3:
                raw = line(5, f"%SYS-5-CONFIG_I: Configured from console by {admin} on vty0 ({src})")
                mnem = "SYS-5-CONFIG_I"
            elif roll < 0.4:
                raw = line(5, f"%SYS-5-CONFIG_NV: Nonvolatile storage configured from console "
                              f"by {admin} on vty0 ({src})")
                mnem = "SYS-5-CONFIG_NV"
            else:
                # Two spaces after the username, and the command text runs to
                # end of line with no delimiter.
                cmd = rng.choice([
                    f"interface {long_if}", "switchport port-security maximum 2",
                    "no logging host 10.20.60.22", "logging trap notifications",
                    "ip access-list extended MGMT-IN", " permit tcp 10.20.10.0 0.0.0.255 any eq 22",
                    "username svc_monitor privilege 5 secret 9 *****"])
                raw = line(5, f"%PARSER-5-CFGLOG_LOGGEDCMD: User:{admin}  logged command:{cmd}")
                mnem = "PARSER-5-CFGLOG_LOGGEDCMD"
            return raw, {"kind": "config", "ios_mnemonic": mnem, "device": dev,
                         "user": admin, "src": src}

        if shape == "portsec":
            if rng.random() < 0.6:
                raw = line(2, f"%PORT_SECURITY-2-PSECURE_VIOLATION: Security violation occurred, "
                              f"caused by MAC address {_ios_mac(mac)} on port {long_if}.")
                mnem = "PORT_SECURITY-2-PSECURE_VIOLATION"
            else:
                raw = line(4, f"%PM-4-ERR_DISABLE: psecure-violation error detected on {short_if}, "
                              f"putting {short_if} in err-disable state")
                mnem = "PM-4-ERR_DISABLE"
            return raw, {"kind": "portsec", "ios_mnemonic": mnem, "device": dev,
                         "mac": mac, "port": long_if}

        if shape == "l2":
            if rng.random() < 0.5:
                raw = line(2, f"%SPANTREE-2-BLOCK_BPDUGUARD: Received BPDU on port {short_if} "
                              f"with BPDU Guard enabled. Disabling port.")
                mnem = "SPANTREE-2-BLOCK_BPDUGUARD"
            else:
                other = f"Gi1/0/{(port % 46) + 2}"
                raw = line(4, f"%SW_MATM-4-MACFLAP_NOTIF: Host {_ios_mac(mac)} in vlan "
                              f"{rng.choice([20, 30, 40])} is flapping between port {short_if} "
                              f"and port {other}")
                mnem = "SW_MATM-4-MACFLAP_NOTIF"
            return raw, {"kind": "l2", "ios_mnemonic": mnem, "device": dev, "mac": mac}

        admin = rng.choice(environment.ADMINS)
        src = environment.ip_for(rng.choice(environment.WORKSTATIONS))
        if rng.random() < 0.5:
            raw = line(4, f"%RADIUS-4-RADIUS_DEAD: RADIUS server "
                          f"{environment.ip_for(rng.choice(ISE_NODES))}:1812,1813 is not responding.")
            mnem = "RADIUS-4-RADIUS_DEAD"
        else:
            raw = line(6, f"%SYS-6-CLOCKUPDATE: System clock has been updated from {_ios_clock(w)} "
                          f"to {_ios_clock(w)}, configured from console by {admin} on vty0 ({src}).")
            mnem = "SYS-6-CLOCKUPDATE"
        return raw, {"kind": "infra", "ios_mnemonic": mnem, "device": dev, "user": admin}


class Ise:
    """ISE RADIUS, accounting, posture, profiler, CoA and TACACS+ syslog.

    The body is a comma-separated key=value list behind a fixed header of
    category, message id, total segments and segment number. Segment totals are
    always 1 here, which is what a target raised to 8192 bytes produces.
    """

    KEY = "cisco_ise"
    SOURCETYPE = "cisco:ise:syslog"
    SOURCE = "/var/log/network/cisco_ise/ise-psn-01/ise-psn-01.log"
    SHARE = 4.5
    CONTROL_FIELD = "ise_code"

    CONTROLS = [
        ("IA-2",    "CSF PR.AA-02", ["5200", "5400"], True, "identification and authentication of users"),
        ("IA-3",    "CSF PR.AA-01", ["5200"], True, "device identification and authentication"),
        ("AC-3",    "CSF PR.AA-05", ["5200"], True, "the authorization profile actually selected"),
        ("AC-7",    "CSF DE.CM-01", ["5400", "5434"], True, "consecutive invalid attempts per endpoint"),
        ("AU-6(3)", "CSF DE.AE-03", ["3000", "3001", "3002"], True,
         "identity-to-address binding that every other repository joins on"),
        ("SI-4(7)", "CSF RS.MI-01", ["5205", "5417"], True,
         "automated response executed, and whether it landed"),
        ("AC-6(9)", "CSF PR.AA-05", ["13005"], True, "per-command record for device administration"),
        ("CM-8(3)", "CSF ID.AM-01", ["80002"], False, "profiling change against the endpoint inventory"),
        ("CM-5(1)", "CSF PR.PS-01", ["58000"], True, "change to the policy that governs network access"),
    ]
    # The interim update is the only record carrying Framed-IP-Address, so
    # dropping 3002 as redundant removes the binding this feed exists for.
    DROPPED_BY_DESIGN = []

    SHAPES = [
        (34.0, "acct"), (30.0, "auth_pass"), (9.0, "auth_fail"), (8.0, "posture"),
        (7.0, "tacacs"), (5.0, "profiler"), (4.0, "coa"), (3.0, "admin"),
    ]

    def emit(self, rng, host, record_id, ts):
        w = _when(ts)
        node = host if host in ISE_NODES else rng.choice(ISE_NODES)
        endpoint = rng.choice(environment.WORKSTATIONS)
        user = rng.choice(environment.USERS)
        dev, port = _switch_for(endpoint)
        nas_ip = environment.ip_for(dev)
        mac = environment.mac_for(endpoint)
        asid = _audit_session(nas_ip, mac, w)
        shape = _pick(rng, self.SHAPES)
        acs_session = f"{node}/{rng.randrange(400000000, 499999999)}/{record_id % 100000}"

        def record(sev, category, code, level, text, fields):
            head = (f"{_pri('ise', sev)}{_ise_header_ts(w)} {node} {category} "
                    f"{record_id % 10**10:010d} 1 0")
            body = (f"{_ise_body_ts(w)} {record_id % 10**10:010d} {code} {level} {text}, "
                    + ", ".join(fields))
            return f"{head} {body}"

        common = [
            f"ConfigVersionId={rng.randrange(100, 199)}",
            f"Device IP Address={nas_ip}",
            f"DestinationIPAddress={environment.ip_for(node)}",
            "DestinationPort=1812",
            f"UserName={user}",
            "Protocol=Radius",
            f"NetworkDeviceName={dev}",
            f"NAS-IP-Address={nas_ip}",
            f"NAS-Port={50000 + port}",
            f"NAS-Port-Id=GigabitEthernet1/0/{port}",
            "NAS-Port-Type=Ethernet",
            f"Called-Station-ID={_ise_mac(environment.mac_for(dev))}",
            f"Calling-Station-ID={_ise_mac(mac)}",
            f"AcsSessionID={acs_session}",
            f"cisco-av-pair=audit-session-id={asid}",
        ]

        if shape == "auth_pass":
            fields = common + [
                f"RequestLatency={rng.randrange(3, 120)}",
                "Service-Type=Framed", "Framed-MTU=1500",
                "AuthenticationIdentityStore=AD-corp",
                "AuthenticationMethod=x509_PKI", "EapAuthentication=EAP-TLS",
                "EapTunnel=EAP-TLS",
                "SelectedAccessService=Default Network Access",
                "AuthenticationPolicyMatchedRule=Wired-Dot1X",
                "AuthorizationPolicyMatchedRule=Corp-Compliant-Workstation",
                "SelectedAuthorizationProfiles=CorpAccess",
                "IdentityGroup=Endpoint Identity Groups:Workstations",
                f"EndPointMACAddress={_ise_mac(mac)}",
                "EndPointMatchedProfile=Microsoft-Workstation",
                f"DACL={DACL}",
                "PostureAssessmentStatus=Compliant",
                "Step=11001", "Step=11017", "Step=15049", "Step=12500", "Step=12800",
                "Step=12805", "Step=12806", "Step=12811", "Step=11503", "Step=11002",
            ]
            raw = record(5, "CISE_Passed_Authentications", "5200", "NOTICE",
                         "Passed-Authentication: Authentication succeeded", fields)
            return raw, {"kind": "auth_pass", "ise_code": "5200", "device": dev,
                         "user": user, "mac": mac, "audit_session_id": asid}

        if shape == "auth_fail":
            roll = rng.random()
            if roll < 0.45:
                code, text, fail = ("5400", "Failed-Attempt: Authentication failed",
                                    "FailureReason=22056 Subject not found in the applicable identity store(s)")
            elif roll < 0.75:
                code, text, fail = ("5400", "Failed-Attempt: Authentication failed",
                                    "FailureReason=24408 User authentication against Active Directory failed "
                                    "since user has entered the wrong password")
            else:
                code, text, fail = ("5434", "RADIUS-Client: Endpoint conducted several failed "
                                            "authentications of the same scenario",
                                    "FailureReason=12514 EAP-TLS failed SSL/TLS handshake because of "
                                    "an unknown CA in the client certificates chain")
            fields = common + [
                fail, "AuthenticationMethod=x509_PKI",
                "AuthenticationIdentityStore=AD-corp",
                "AuthenticationPolicyMatchedRule=Wired-Dot1X",
                "SelectedAuthorizationProfiles=Quarantine",
                f"EndPointMACAddress={_ise_mac(mac)}",
                "Step=11001", "Step=11017", "Step=12500", "Step=12805", "Step=11504",
            ]
            raw = record(5, "CISE_Failed_Attempts", code, "NOTICE", text, fields)
            return raw, {"kind": "auth_fail", "ise_code": code, "device": dev,
                         "user": user, "mac": mac, "audit_session_id": asid}

        if shape == "acct":
            roll = rng.random()
            if roll < 0.08:
                code, text = "3000", "Radius-Accounting: RADIUS Accounting start request"
                extra = ["Acct-Status-Type=Start"]
            elif roll < 0.16:
                code, text = "3001", "Radius-Accounting: RADIUS Accounting stop request"
                extra = ["Acct-Status-Type=Stop",
                         f"Acct-Session-Time={rng.randrange(60, 36000)}",
                         f"Acct-Input-Octets={rng.randrange(10**4, 10**9)}",
                         f"Acct-Output-Octets={rng.randrange(10**4, 10**9)}",
                         f"Acct-Terminate-Cause={rng.choice(['Lost-Carrier', 'User-Request', 'Session-Timeout'])}",
                         f"Framed-IP-Address={environment.ip_for(endpoint)}"]
            else:
                code, text = "3002", "Radius-Accounting: RADIUS Accounting watchdog update"
                extra = ["Acct-Status-Type=Interim-Update",
                         f"Acct-Session-Time={rng.randrange(60, 36000)}",
                         f"Framed-IP-Address={environment.ip_for(endpoint)}"]
            fields = common + extra + [
                f"Acct-Session-Id={record_id % 10**8:08X}",
                f"EndPointMACAddress={_ise_mac(mac)}",
            ]
            raw = record(5, "CISE_RADIUS_Accounting", code, "NOTICE", text, fields)
            return raw, {"kind": "acct", "ise_code": code, "device": dev, "user": user,
                         "mac": mac, "audit_session_id": asid,
                         "src": environment.ip_for(endpoint)}

        if shape == "posture":
            compliant = rng.random() > 0.12
            fields = common + [
                f"PostureStatus={'Compliant' if compliant else 'NonCompliant'}",
                f"EndPointMACAddress={_ise_mac(mac)}",
                "PostureModuleVersion=5.1.2.42", "OPSWATComplianceModule=4.3.3556.0",
                f"AntiMalwareDefinitionDate={w.strftime('%Y-%m-%d')}",
                f"FirewallStatus={'Enabled' if compliant else 'Disabled'}",
                f"DiskEncryptionStatus={'Encrypted' if compliant else 'NotEncrypted'}",
                f"FailedConditions={'' if compliant else 'ANY_AM_DEFINITION_7DAYS'}",
            ]
            raw = record(5, "CISE_Posture_and_Client_Provisioning_Audit", "86009", "NOTICE",
                         "Posture: Received a posture report from an endpoint", fields)
            return raw, {"kind": "posture", "ise_code": "86009", "device": dev,
                         "user": user, "mac": mac, "audit_session_id": asid}

        if shape == "coa":
            ok = rng.random() > 0.18
            code = "5205" if ok else "5417"
            text = ("Dynamic-Authorization: Dynamic Authorization succeeded" if ok else
                    "Dynamic-Authorization: Dynamic Authorization failed")
            fields = common + [
                f"CoA-Type={rng.choice(['Reauth', 'Port Bounce', 'Disconnect'])}",
                "CoA-Source=Adaptive Network Control",
                f"SelectedAuthorizationProfiles={QUARANTINE_DACL}",
                f"EndPointMACAddress={_ise_mac(mac)}",
            ] + ([] if ok else ["FailureReason=11213 No response received from Network Access Device "
                                "after sending a Dynamic Authorization request"])
            raw = record(5, "CISE_RADIUS_Diagnostics", code, "NOTICE", text, fields)
            return raw, {"kind": "coa", "ise_code": code, "device": dev,
                         "mac": mac, "audit_session_id": asid}

        if shape == "profiler":
            fields = [
                f"ConfigVersionId={rng.randrange(100, 199)}",
                f"EndpointMACAddress={_ise_mac(mac)}",
                f"EndpointNADAddress={nas_ip}",
                f"EndpointPolicy={rng.choice(['Microsoft-Workstation', 'Cisco-IP-Phone-8841', 'HP-Printer'])}",
                "EndpointMatchedProfile=Microsoft-Workstation",
                "EndpointSourceEvent=RADIUS Probe",
                "EndpointIdentityGroup=Workstations",
                f"EndpointIPAddress={environment.ip_for(endpoint)}",
            ]
            raw = record(5, "CISE_Profiler", "80002", "NOTICE",
                         "Profiler: Profiler EndPoint profiling event occurred", fields)
            return raw, {"kind": "profiler", "ise_code": "80002", "device": dev, "mac": mac}

        if shape == "tacacs":
            admin = rng.choice(environment.ADMINS)
            target = rng.choice(SWITCHES + ROUTERS + ASA_DEVICES)
            denied = rng.random() < 0.1
            cmd = rng.choice(["show running-config", "show archive log config all",
                              "configure terminal", "show logging", "clear logging",
                              "copy running-config tftp:"])
            fields = [
                f"ConfigVersionId={rng.randrange(100, 199)}",
                f"Device IP Address={environment.ip_for(target)}",
                f"NetworkDeviceName={target}",
                "NetworkDeviceGroups=Device Type#All Device Types#Switch",
                f"User={admin}", f"UserName={admin}",
                f"RemoteAddress={environment.ip_for(rng.choice(environment.WORKSTATIONS))}",
                "Type=Command Authorization", "Privilege-Level=15",
                f"CmdAV={cmd}", "CmdArgAV=<cr>",
                "ShellProfile=NetworkAdmin",
                f"MatchedCommandSet={'ReadOnly' if denied else 'FullAccess'}",
                f"AuthorizationResult={'Deny' if denied else 'PassAdd'}",
                f"AcsSessionID={acs_session}",
            ]
            raw = record(5, "CISE_TACACS_Accounting", "13005", "NOTICE",
                         "Tacacs-Accounting: TACACS+ Accounting with Command", fields)
            return raw, {"kind": "tacacs", "ise_code": "13005", "device": target, "user": admin}

        admin = rng.choice(environment.ADMINS)
        obj = rng.choice(["Authorization Profile", "Policy Set", "Downloadable ACL",
                          "Command Set", "Internal User", "Network Device"])
        fields = [
            f"ConfigVersionId={rng.randrange(100, 199)}",
            f"AdminName={admin}",
            f"AdminIPAddress={environment.ip_for(rng.choice(environment.WORKSTATIONS))}",
            "AdminInterface=GUI", f"ObjectType={obj}",
            f"ObjectName={rng.choice(['CorpAccess', 'Wired-Dot1X', DACL, 'NetworkAdmin'])}",
            f"OperationMessageText={rng.choice(['Created', 'Updated', 'Deleted'])} {obj}",
            "Requester=Admin",
        ]
        raw = record(5, "CISE_Administrative_and_Operational_Audit", "58000", "NOTICE",
                     "Configuration-Changes: Object is changed", fields)
        return raw, {"kind": "admin", "ise_code": "58000", "device": node, "user": admin}


ASA = Asa()
IOS = Ios()
ISE = Ise()
ALL = [ASA, IOS, ISE]
