"""
Shared emitter harness for the enterprise log data set.

One process plays a whole environment. Each source module declares its own record
shape, sourcetype and relative volume, and this file does everything that is
not source-specific: weighted selection, rate pacing, the A/B tee, and the byte
accounting both arms are measured against.

The tee is what makes the measurement an experiment rather than an assertion.
Every record goes twice: once into Cribl over mutual TLS, and once straight to
Splunk HEC into a control index. Both arms are then read back out of Splunk the
same way, so the "no pipeline" baseline is measured rather than computed.
"""

import json
import random
import socket
import ssl
import sys
import time
import urllib.request


class Accounting:
    """Bytes and counts per source, which is the unit the report is built on."""

    def __init__(self):
        self.by_source = {}
        self.total_bytes = 0
        self.total_events = 0

    def add(self, key, nbytes):
        slot = self.by_source.setdefault(key, [0, 0])
        slot[0] += 1
        slot[1] += nbytes
        self.total_events += 1
        self.total_bytes += nbytes

    def report(self):
        lines = [f"dataset_total events={self.total_events} bytes={self.total_bytes}"]
        for key in sorted(self.by_source, key=lambda k: -self.by_source[k][1]):
            n, b = self.by_source[key]
            lines.append(f"dataset_source {key} {n} {b}")
        return lines


class DirectHec:
    """The control arm: the same records, straight to Splunk, nothing removed.

    Failures never stop the run - the Cribl path is what the lab exercises -
    but they are counted, because a silent baseline of zero would read as a
    perfect saving.
    """

    def __init__(self, url, token, index, ca=None, batch=200):
        self.url, self.token, self.index, self.batch = url, token, index, batch
        self.ctx = ssl.create_default_context(cafile=ca) if url.startswith("https") else None
        self.buf, self.sent, self.errors, self.last_error = [], 0, 0, ""

    def add(self, host, source, sourcetype, raw, epoch=None):
        evt = {"event": raw, "host": host, "source": source,
               "sourcetype": sourcetype, "index": self.index}
        if epoch is not None:
            evt["time"] = epoch
        self.buf.append(json.dumps(evt))
        if len(self.buf) >= self.batch:
            self.flush()

    def flush(self):
        if not self.buf:
            return
        # Newline-delimited objects, never a JSON array: an array body is
        # rejected with code 6 and the whole batch is lost.
        body = "\n".join(self.buf).encode()
        req = urllib.request.Request(
            self.url, data=body, headers={"Authorization": "Splunk " + self.token})
        try:
            urllib.request.urlopen(req, context=self.ctx, timeout=30).read()
            self.sent += len(self.buf)
        except Exception as exc:
            self.errors += len(self.buf)
            self.last_error = f"{type(exc).__name__}: {exc}"
        self.buf = []


def connect(host, port, ctx, attempts=30):
    for _ in range(attempts):
        try:
            sock = socket.create_connection((host, port), 10)
            return ctx.wrap_socket(sock, server_hostname=host) if ctx else sock
        except OSError as exc:
            print(f"connect {host}:{port} failed ({exc}); retrying", flush=True)
            time.sleep(2)
    return None


def calibrate(sources, rng, host_for, samples=400):
    """Average record size per source, measured from the source itself.

    SHARE is declared as a share of environment BYTES, because that is how SIEM
    volume is quoted and licensed. Records differ in size by a factor of six
    across these sources, so a byte share cannot be turned into a selection
    weight without knowing each source's average size. Measure it rather than
    hardcode it, or every edit to a record shape silently changes the mix.
    """
    avg = {}
    for mod in sources:
        total = 0
        for i in range(samples):
            raw, _ = mod.emit(rng, host_for(mod, rng), i + 1, "2026-01-01T00:00:00.000Z")
            total += len(raw.encode())
        avg[mod.KEY] = max(total / samples, 1.0)
    return avg


def weighted_picker(sources, rng, avg_bytes=None):
    """Pick a source so the data set lands on the declared BYTE shares.

    Selection is per record, so the event weight is the byte share divided by
    the average record size. Without avg_bytes this falls back to treating
    SHARE as an event weight.
    """
    keys = [s.KEY for s in sources]
    if avg_bytes:
        weights = [max(float(getattr(s, "SHARE", 1)), 0.0) / avg_bytes[s.KEY] for s in sources]
    else:
        weights = [max(float(getattr(s, "SHARE", 1)), 0.0) for s in sources]
    if sum(weights) <= 0:
        weights = [1.0] * len(sources)
    index = {s.KEY: s for s in sources}
    return lambda: index[rng.choices(keys, weights=weights, k=1)[0]]
