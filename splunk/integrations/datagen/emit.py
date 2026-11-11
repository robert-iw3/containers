#!/usr/bin/env python3

"""Deliver generated events over whichever path you need to test.

datagen.py writes files, which covers a monitor input. Everything else a
Splunk environment can receive data through has different behavior worth
testing on its own: HEC applies per-event metadata from JSON, a TCP syslog
input depends on framing, UDP silently drops what it cannot keep up with,
and index-time routing keys on metadata that only some paths carry.

So the destination is a URI, and more than one can be given at once:

  file:///var/tmp/out                       one file per source type
  hec://TOKEN@host:8088                     HTTP Event Collector, event endpoint
  hec://TOKEN@host:8088?raw=1               raw endpoint, metadata in the query
  tcp://host:514                            newline-framed
  tcp://host:514?framing=octet              octet-counted, RFC 6587
  udp://host:514                            one datagram per event
  stdout://                                 for a scripted input, or a pipe

Run --preflight first. It probes each destination and names what is not
configured yet rather than failing part-way through a run.

Volume is either a record count or a rate. A rate with a duration is the
load test; a count is the functional one.

Standard library only.
"""

import argparse
import importlib.util
import json
import random
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent


def load_datagen():
    spec = importlib.util.spec_from_file_location("datagen", HERE / "datagen.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DG = load_datagen()


class Probe:
    """One preflight finding. 'todo' is what the operator has to do."""

    def __init__(self, ok, destination, detail, todo=""):
        self.ok = ok
        self.destination = destination
        self.detail = detail
        self.todo = todo

    def __str__(self):
        mark = "OK  " if self.ok else "BLOCKED"
        out = f"{mark:<8} {self.destination}\n         {self.detail}"
        if self.todo:
            out += f"\n         to do: {self.todo}"
        return out


# ----------------------------------------------------------------- sinks

class Sink:
    scheme = ""

    def __init__(self, uri, opts):
        self.uri = uri
        self.p = urlparse(uri)
        self.q = {k: v[0] for k, v in parse_qs(self.p.query).items()}
        self.opts = opts
        self.sent = 0
        self.bytes = 0
        self.errors = Counter()

    def preflight(self):
        return [Probe(True, self.uri, "no checks for this destination")]

    def send(self, line, meta):
        raise NotImplementedError

    def flush(self):
        pass

    def close(self):
        self.flush()

    def _host_port(self, default_port):
        return self.p.hostname, (self.p.port or default_port)

    def tcp_probe(self, host, port, what):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.opts["timeout"])
        try:
            s.connect((host, port))
            return Probe(True, self.uri, f"{what} accepts connections on {host}:{port}")
        except Exception as e:
            return Probe(False, self.uri,
                         f"cannot reach {host}:{port} ({type(e).__name__})",
                         f"confirm {what} is enabled and listening, and that this "
                         f"host can route to {host}. In rootless podman a container "
                         f"network is not reachable from the host, so run the "
                         f"emitter inside the container or publish the port.")
        finally:
            s.close()


class FileSink(Sink):
    scheme = "file"

    def __init__(self, uri, opts):
        super().__init__(uri, opts)
        self.dir = Path(self.p.path or "./datagen-out")
        self.handles = {}

    def preflight(self):
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            probe = self.dir / ".datagen-write-test"
            probe.write_text("x", encoding="utf-8")
            probe.unlink()
        except Exception as e:
            return [Probe(False, self.uri, f"cannot write to {self.dir}: {e}",
                          "create the directory, or choose one this account can write")]
        return [Probe(True, self.uri, f"{self.dir} is writable",
                      "a forwarder still has to monitor this path; emit.py writes "
                      "an inputs.conf beside the data")]

    def send(self, line, meta):
        st = meta["sourcetype"]
        fh = self.handles.get(st)
        if fh is None:
            self.dir.mkdir(parents=True, exist_ok=True)
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", st) + ".log"
            fh = open(self.dir / name, "a", encoding="utf-8")
            self.handles[st] = fh
        fh.write(line + "\n")
        self.sent += 1
        self.bytes += len(line) + 1

    def flush(self):
        for fh in self.handles.values():
            fh.flush()

    def close(self):
        self.flush()
        for fh in self.handles.values():
            fh.close()
        self.handles.clear()


class HecSink(Sink):
    scheme = "hec"

    def __init__(self, uri, opts):
        super().__init__(uri, opts)
        self.token = self.p.username or self.q.get("token", "")
        self.host, self.port = self._host_port(8088)
        self.raw = self.q.get("raw", "0") == "1"
        self.insecure = self.q.get("insecure", "1") == "1"
        self.channel = self.q.get("channel") or str(uuid.uuid4())
        scheme = "http" if self.q.get("scheme") == "http" else "https"
        self.base = f"{scheme}://{self.host}:{self.port}"
        self.batch = []
        self.batch_bytes = 0
        self.ctx = ssl.create_default_context()
        if self.insecure:
            # A lab indexer uses a self-signed certificate. This is opt-out,
            # not a default for anything outside a test environment.
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def _post(self, path, body, headers, timeout=None):
        req = urllib.request.Request(self.base + path, data=body, headers=headers,
                                     method="POST")
        return urllib.request.urlopen(req, timeout=timeout or self.opts["timeout"],
                                      context=self.ctx)

    def preflight(self):
        out = [self.tcp_probe(self.host, self.port, "HEC")]
        if not out[0].ok:
            return out
        # The health endpoint needs no token, so it separates "HEC is off"
        # from "the token is wrong".
        try:
            req = urllib.request.Request(self.base + "/services/collector/health")
            r = urllib.request.urlopen(req, timeout=self.opts["timeout"], context=self.ctx)
            out.append(Probe(True, self.uri, f"HEC health returned {r.status}"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 403):
                out.append(Probe(True, self.uri,
                                 f"HEC is listening (health returned {e.code})"))
            else:
                out.append(Probe(False, self.uri, f"HEC health returned {e.code}",
                                 "enable the HTTP Event Collector: set disabled = 0 "
                                 "in the [http] stanza of an app's inputs.conf, then "
                                 "restart splunkd"))
                return out
        except Exception as e:
            out.append(Probe(False, self.uri, f"HEC health unreachable: {type(e).__name__}",
                             "enable the HTTP Event Collector and restart splunkd"))
            return out
        if not self.token:
            out.append(Probe(False, self.uri, "no token given",
                             "pass hec://TOKEN@host:8088; create the token with an "
                             "[http://<name>] stanza in inputs.conf"))
            return out
        # One real event, so a bad token or a disallowed index is found now.
        try:
            body = json.dumps({"event": "datagen preflight",
                               "sourcetype": "datagen:preflight",
                               "index": self.opts["index"]}).encode()
            r = self._post("/services/collector/event",
                           body, {"Authorization": f"Splunk {self.token}",
                                  "Content-Type": "application/json"})
            payload = json.loads(r.read().decode() or "{}")
            if payload.get("code") == 0:
                out.append(Probe(True, self.uri,
                                 f"token accepted, index {self.opts['index']!r} allowed"))
            else:
                out.append(Probe(False, self.uri, f"HEC replied {payload}",
                                 "check the token and its allowed indexes"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:160]
            todo = "check the token value"
            if "index" in detail.lower():
                todo = (f"allow index {self.opts['index']!r} on the token: set "
                        f"index/indexes in the [http://<name>] stanza, or create "
                        f"the index")
            out.append(Probe(False, self.uri, f"HTTP {e.code}: {detail}", todo))
        except Exception as e:
            out.append(Probe(False, self.uri, f"{type(e).__name__}: {e}", ""))
        return out

    def send(self, line, meta):
        if self.raw:
            self.batch.append(line)
        else:
            self.batch.append(json.dumps({
                "time": meta["time"], "host": meta["host"], "source": meta["source"],
                "sourcetype": meta["sourcetype"], "index": meta["index"],
                "event": line,
            }, separators=(",", ":")))
        self.batch_bytes += len(line) + 1
        if len(self.batch) >= self.opts["batch"] or self.batch_bytes > 800_000:
            self.flush()

    def flush(self):
        if not self.batch:
            return
        body = ("\n".join(self.batch) + "\n").encode("utf-8")
        headers = {"Authorization": f"Splunk {self.token}",
                   "X-Splunk-Request-Channel": self.channel}
        path = "/services/collector/event"
        if self.raw:
            # The raw endpoint carries metadata in the query string, because
            # the body is the event text with no envelope.
            from urllib.parse import urlencode
            path = "/services/collector/raw?" + urlencode({
                "sourcetype": self.opts["raw_sourcetype"] or "datagen:raw",
                "index": self.opts["index"],
                "host": self.opts["raw_host"] or socket.gethostname(),
            })
            headers["Content-Type"] = "text/plain"
        else:
            headers["Content-Type"] = "application/json"
        n = len(self.batch)
        try:
            r = self._post(path, body, headers, timeout=self.opts["timeout"] * 2)
            r.read()
            self.sent += n
            self.bytes += len(body)
        except urllib.error.HTTPError as e:
            self.errors[f"HTTP {e.code}: {e.read().decode(errors='replace')[:90]}"] += n
        except Exception as e:
            self.errors[f"{type(e).__name__}: {e}"] += n
        self.batch.clear()
        self.batch_bytes = 0


class TcpSink(Sink):
    scheme = "tcp"

    def __init__(self, uri, opts):
        super().__init__(uri, opts)
        self.host, self.port = self._host_port(514)
        self.framing = self.q.get("framing", "lf")
        self.sock = None

    def preflight(self):
        out = [self.tcp_probe(self.host, self.port, "the TCP input")]
        if out[0].ok:
            out.append(Probe(True, self.uri,
                             f"framing={self.framing}",
                             "the receiving input decides the source type, so set it "
                             "on the [tcp://PORT] stanza; octet framing needs a "
                             "syslog-aware input"))
        else:
            out[0].todo = ("add a [tcp://%d] stanza with a sourcetype and index to "
                           "an app's inputs.conf, then restart splunkd" % self.port)
        return out

    def _connect(self):
        if self.sock is None:
            self.sock = socket.create_connection((self.host, self.port),
                                                 timeout=self.opts["timeout"])

    def send(self, line, meta):
        try:
            self._connect()
            payload = (f"{len(line.encode())} {line}".encode() if self.framing == "octet"
                       else (line + "\n").encode())
            self.sock.sendall(payload)
            self.sent += 1
            self.bytes += len(payload)
        except Exception as e:
            self.errors[f"{type(e).__name__}: {e}"] += 1
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class UdpSink(Sink):
    scheme = "udp"

    def __init__(self, uri, opts):
        super().__init__(uri, opts)
        self.host, self.port = self._host_port(514)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.oversize = 0

    def preflight(self):
        # UDP gives no delivery signal at all, so resolution is all that can
        # be established before sending.
        try:
            socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_DGRAM)
        except Exception as e:
            return [Probe(False, self.uri, f"cannot resolve {self.host}: {e}",
                          "check the hostname")]
        return [Probe(True, self.uri, f"{self.host}:{self.port} resolves",
                      "UDP is unacknowledged: a send succeeding does not mean the "
                      "input received it. Confirm with the receiver's metrics, and "
                      "add a [udp://%d] stanza if there is none." % self.port)]

    def send(self, line, meta):
        data = line.encode("utf-8")
        if len(data) > self.opts["udp_max"]:
            # A datagram over the input's maxEventSize is truncated or
            # dropped, so it is counted rather than silently sent.
            self.oversize += 1
            data = data[:self.opts["udp_max"]]
        try:
            self.sock.sendto(data, (self.host, self.port))
            self.sent += 1
            self.bytes += len(data)
        except Exception as e:
            self.errors[f"{type(e).__name__}: {e}"] += 1

    def close(self):
        self.sock.close()


class StdoutSink(Sink):
    scheme = "stdout"

    def preflight(self):
        return [Probe(True, self.uri, "writes to standard output",
                      "a scripted input reads stdout; set the source type on the "
                      "[script://] stanza")]

    def send(self, line, meta):
        sys.stdout.write(line + "\n")
        self.sent += 1
        self.bytes += len(line) + 1

    def flush(self):
        sys.stdout.flush()


SINKS = {s.scheme: s for s in (FileSink, HecSink, TcpSink, UdpSink, StdoutSink)}


def make_sink(uri, opts):
    scheme = urlparse(uri).scheme
    if scheme not in SINKS:
        sys.exit(f"unsupported destination {uri!r}; schemes: "
                 f"{', '.join(sorted(SINKS))}")
    return SINKS[scheme](uri, opts)


# ------------------------------------------------------------------ main

def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--templates", default=str(HERE / "templates"))
    ap.add_argument("--to", action="append", required=True,
                    help="Destination URI; repeatable")
    ap.add_argument("--records", type=int, default=0,
                    help="Send this many records, then stop")
    ap.add_argument("--rate", type=float, default=0.0,
                    help="Records per second; use with --duration for a load test")
    ap.add_argument("--duration", type=float, default=0.0,
                    help="Seconds to keep sending at --rate")
    ap.add_argument("--index", default="main",
                    help="Index metadata on each event, where the path carries it")
    ap.add_argument("--hosts", type=int, default=1,
                    help="Distinct host values, for routing and cardinality tests")
    ap.add_argument("--sources", type=int, default=1, help="Distinct source values")
    ap.add_argument("--host-prefix", default="datagen-host")
    ap.add_argument("--source-prefix", default="datagen:source")
    ap.add_argument("--only", action="append", default=None,
                    help="Restrict to this template name; repeatable")
    ap.add_argument("--window-hours", type=float, default=0.25,
                    help="Spread event timestamps over this many hours")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--batch", type=int, default=200, help="HEC events per request")
    ap.add_argument("--timeout", type=float, default=10.0, help="Network timeout")
    ap.add_argument("--udp-max", type=int, default=1024,
                    help="Truncate a datagram at this size, matching the input's "
                         "maxEventSize default")
    ap.add_argument("--raw-sourcetype", default=None,
                    help="Source type for the HEC raw endpoint, which cannot take "
                         "it per event")
    ap.add_argument("--raw-host", default=None)
    ap.add_argument("--preflight", action="store_true",
                    help="Probe every destination and report what is not configured, "
                         "without sending anything")
    args = ap.parse_args(argv[1:])

    opts = {"batch": args.batch, "timeout": args.timeout, "index": args.index,
            "udp_max": args.udp_max, "raw_sourcetype": args.raw_sourcetype,
            "raw_host": args.raw_host}
    sinks = [make_sink(u, opts) for u in args.to]

    print("Preflight")
    probes = []
    for s in sinks:
        probes.extend(s.preflight())
    for p in probes:
        print(p)
    blocked = [p for p in probes if not p.ok]
    print(f"\n{len(probes) - len(blocked)} of {len(probes)} check(s) passed")

    if args.preflight:
        return 1 if blocked else 0
    if blocked:
        print("\nRefusing to send while a destination is unreachable. "
              "Fix the items above, or drop that --to.", file=sys.stderr)
        for s in sinks:
            s.close()
        return 1

    # Validate templates before sending, for the same reason datagen does.
    import subprocess
    validator = HERE / "validate-templates.py"
    if validator.exists():
        rc = subprocess.run([sys.executable, str(validator),
                             "--templates", args.templates, "--quiet"]).returncode
        if rc != 0:
            print("template validation failed; run validate-templates.py",
                  file=sys.stderr)
            return rc

    templates = DG.load_templates(Path(args.templates))
    if args.only:
        templates = [t for t in templates if t["name"] in set(args.only)]
        if not templates:
            sys.exit(f"no template matched --only {args.only}")

    if not args.records and not (args.rate and args.duration):
        sys.exit("give --records N, or --rate R with --duration S")

    rng = random.Random(args.seed)
    seq_state = {}
    now = datetime.now(timezone.utc)
    window = args.window_hours * 3600
    pool = [t for t in templates for _ in range(max(1, int(t.get("weight", 10))))]
    hosts = [f"{args.host_prefix}-{i:02d}" for i in range(1, max(1, args.hosts) + 1)]
    sources = [f"{args.source_prefix}:{i:02d}" for i in range(1, max(1, args.sources) + 1)]

    target = args.records if args.records else None
    deadline = (time.monotonic() + args.duration) if args.duration else None
    interval = (1.0 / args.rate) if args.rate else 0.0

    print(f"\nSending to {len(sinks)} destination(s)")
    if target:
        print(f"  {target:,} records")
    else:
        print(f"  {args.rate:,.0f} records/second for {args.duration:,.0f}s "
              f"(about {int(args.rate * args.duration):,} records)")
    print(f"  index={args.index} hosts={len(hosts)} sources={len(sources)}")

    started = time.monotonic()
    produced = 0
    next_due = started
    try:
        while True:
            if target is not None and produced >= target:
                break
            if deadline is not None and time.monotonic() >= deadline:
                break
            t = rng.choice(pool)
            lines = DG.emit_once(t, rng, seq_state, now, window)
            for line in lines:
                meta = {
                    "sourcetype": t["sourcetype"], "index": args.index,
                    "host": rng.choice(hosts), "source": rng.choice(sources),
                    "time": time.time(),
                }
                for s in sinks:
                    s.send(line, meta)
                produced += 1
                if target is not None and produced >= target:
                    break
            if interval:
                next_due += interval * len(lines)
                sleep_for = next_due - time.monotonic()
                if sleep_for > 0:
                    time.sleep(sleep_for)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
    finally:
        for s in sinks:
            s.close()

    elapsed = max(1e-6, time.monotonic() - started)
    print(f"\n{'destination':<46} {'sent':>10} {'MB':>8} {'rec/s':>9} {'errors':>8}")
    total_err = 0
    for s in sinks:
        errs = sum(s.errors.values())
        total_err += errs
        print(f"{s.uri:<46} {s.sent:>10,} {s.bytes/1048576:>8.2f} "
              f"{s.sent/elapsed:>9,.0f} {errs:>8,}")
    print(f"{'produced':<46} {produced:>10,} {'':>8} {produced/elapsed:>9,.0f}")
    print(f"elapsed {elapsed:,.1f}s")

    for s in sinks:
        if s.errors:
            print(f"\n{s.uri} errors:")
            for msg, n in s.errors.most_common(5):
                print(f"  {n:>7,}x {msg}")
        if isinstance(s, UdpSink) and s.oversize:
            print(f"\n{s.uri}: {s.oversize:,} datagram(s) truncated at "
                  f"{args.udp_max} bytes; raise maxEventSize on the input "
                  f"or lower --udp-max")

    if isinstance(sinks[0], FileSink):
        pass
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
