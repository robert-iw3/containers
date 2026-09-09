#!/usr/bin/env python3
"""
Emit a realistic enterprise log environment into Cribl, and the same records
straight into Splunk as the control arm.

Fifteen sources, weighted the way an enterprise SIEM is weighted, each
declaring which NIST SP 800-53r5 controls and CSF 2.0 subcategories its events
evidence. That declaration is what makes the reduction measurable as a trade
rather than as a percentage: the lab asserts, after reduction, that every
control's evidence still arrived.

  --out-dir          write one file per sourcetype for a forwarder to tail
                     (the production path: UF -> Cribl S2S -> Splunk)
  --host/--port      the Cribl tcpjson Source, when not using --out-dir
  --count            total records across all sources
  --rate             records per second, all sources together
  --ca/--cert/--key  mutual TLS to Cribl
  environment        SPLUNK_HEC_URL / SPLUNK_HEC_TOKEN / SPLUNK_HEC_INDEX for
                     the control arm, kept out of the process list
"""

import argparse
import json
import os
import random
import ssl
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import environment                                   # noqa: E402
from harness import Accounting, DirectHec, calibrate, connect, weighted_picker  # noqa: E402
import sources                                  # noqa: E402


def host_for(mod, rng):
    """Which machine a source's records claim to come from.

    A firewall log does not come from a workstation, and getting this wrong
    makes every host-based correlation in the data set meaningless.
    """
    if mod.KEY in ("win_security", "sysmon"):
        return rng.choice(environment.WORKSTATIONS * 4 + environment.SERVERS + environment.DCS)
    if mod.KEY == "win_dns":
        return rng.choice(environment.DCS)
    if mod.KEY == "linux_audit":
        return rng.choice(environment.LINUX)
    if mod.KEY == "pan_firewall":
        return "pan-fw01"
    if mod.KEY == "suricata":
        return "ids-core-01"
    if mod.KEY == "cisco_ise":
        return "ise-psn-01"
    if mod.KEY == "asa_vpn":
        return "asa-vpn-01"
    if mod.KEY == "proxy":
        return "proxy-01"
    return "graph.microsoft.com"


def main():
    ap = argparse.ArgumentParser(description="Enterprise log sources -> Cribl")
    ap.add_argument("--host", default="cribl-worker")
    ap.add_argument("--port", type=int, default=10060)
    ap.add_argument("--rate", type=int, default=400, help="records per second, all sources")
    ap.add_argument("--count", type=int, default=20000, help="total records, 0 = forever")
    ap.add_argument("--seed", type=int, default=0, help="0 uses a fixed seed for a repeatable data set")
    ap.add_argument("--ca")
    ap.add_argument("--cert")
    ap.add_argument("--key")
    ap.add_argument("--server-name", dest="server_name")
    # The production path. A universal forwarder tails these files and its
    # tcpout clones every record to both destinations, so Splunk itself
    # performs the A/B tee and both arms travel the same transport.
    ap.add_argument("--out-dir", dest="out_dir",
                    help="write one file per sourcetype instead of opening a socket")
    args = ap.parse_args()

    # A fixed seed by default. The data set has to be the same between the A and
    # B arms of one run, and comparable between runs; a reduction figure that
    # moves because the dice moved is not a measurement.
    rng = random.Random(args.seed or 1729)

    mods = sources.ALL
    # Calibrate on a throwaway RNG so the data set itself is unaffected by it.
    avg = calibrate(mods, random.Random(7), host_for)
    pick = weighted_picker(mods, rng, avg)
    acct = Accounting()

    hec = None
    if os.environ.get("SPLUNK_HEC_URL") and os.environ.get("SPLUNK_HEC_TOKEN"):
        hec = DirectHec(os.environ["SPLUNK_HEC_URL"], os.environ["SPLUNK_HEC_TOKEN"],
                        os.environ.get("SPLUNK_HEC_INDEX", "enterprise_raw"),
                        os.environ.get("SPLUNK_HEC_CA") or None)

    ctx = None
    if args.ca or args.cert:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=args.ca)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        if args.cert:
            ctx.load_cert_chain(args.cert, args.key)

    sock = None
    files = {}
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        for mod in mods:
            files[mod.KEY] = open(os.path.join(args.out_dir, f"{mod.KEY}.log"), "a",
                                  buffering=1, encoding="utf-8")
        print(f"writing {len(mods)} files to {args.out_dir} for a forwarder to tail, "
              f"{args.rate}/s", flush=True)
    else:
        sock = connect(args.host, args.port, ctx)
        if sock is None:
            print("could not connect", file=sys.stderr)
            return 1
        print(f"connected to {args.host}:{args.port} over {'tls' if ctx else 'tcp'}, "
              f"{len(mods)} sources, {args.rate}/s", flush=True)

    # Timestamps advance with the run so _time is the event's own time on both
    # arms, not the moment Splunk happened to index it.
    base = datetime.now(timezone.utc) - timedelta(seconds=args.count / max(args.rate, 1))
    interval = 1.0 / max(args.rate, 1)
    counters = {}
    sent = 0
    try:
        while args.count == 0 or sent < args.count:
            mod = pick()
            host = host_for(mod, rng)
            counters[mod.KEY] = counters.get(mod.KEY, 0) + 1
            when = base + timedelta(seconds=sent * interval)
            ts = when.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            epoch = when.timestamp()
            raw, meta = mod.emit(rng, host, counters[mod.KEY], ts)
            acct.add(mod.KEY, len(raw.encode()))
            if files:
                # One physical line per record. A record containing a newline
                # would break the forwarder's line breaking, so it is escaped
                # here rather than left to props.conf at the far end.
                files[mod.KEY].write(raw.replace("\n", "\\n") + "\n")
            else:
                line = json.dumps({
                    "host": host, "source": mod.SOURCE, "sourcetype": mod.SOURCETYPE,
                    "index": "enterprise", "_time": epoch, "_raw": raw,
                })
                sock.sendall((line + "\n").encode())
                if hec is not None:
                    hec.add(host, mod.SOURCE, mod.SOURCETYPE, raw, epoch)
            sent += 1
            if sent % 5000 == 0:
                print(f"sent {sent}", flush=True)
            time.sleep(interval)
    except (BrokenPipeError, ConnectionResetError) as exc:
        print(f"connection lost after {sent} events: {exc}", file=sys.stderr)
        return 1
    finally:
        for f in files.values():
            try:
                f.close()
            except OSError:
                pass
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    if hec is not None:
        hec.flush()
        print(f"direct_hec sent={hec.sent} errors={hec.errors}", flush=True)
        if hec.last_error:
            print(f"direct_hec last_error {hec.last_error}", flush=True)

    for line in acct.report():
        print(line, flush=True)
    # The control manifest the lab asserts against after reduction.
    manifest = []
    for mod in mods:
        for control, csf, events, must, why in getattr(mod, "CONTROLS", []):
            manifest.append({"control": control, "csf": csf, "source": mod.KEY,
                             "sourcetype": mod.SOURCETYPE,
                             "field": getattr(mod, "CONTROL_FIELD", None),
                             "events": [str(e) for e in events],
                             "must_not_drop": must, "why": why})
    print("control_manifest " + json.dumps(manifest), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
