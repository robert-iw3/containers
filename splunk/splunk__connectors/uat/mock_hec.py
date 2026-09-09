"""
A HEC endpoint that rejects what Splunk's HEC rejects.

The point of this file is to fail a connector that a permissive receiver would
pass. Anything that accepts JSON and returns 200 will call a broken connector
healthy, so every rule below is one Splunk enforces and one a connector can
plausibly get wrong.

Rules, and the Splunk response for each:

  no Authorization header      401  {"text":"Token is required","code":2}
  wrong token                  403  {"text":"Invalid token","code":4}
  empty body                   400  {"text":"No data","code":5}
  body is a JSON array         400  {"text":"Invalid data format","code":6}
  object without "event"       400  {"text":"No data","code":5}
  non-numeric "time"           400  {"text":"Invalid data format","code":6}
  otherwise                    200  {"text":"Success","code":0}

The array rule is the one that matters most here. HEC reads a body as a stream
of concatenated or newline-separated JSON OBJECTS, not as a JSON array, so
json.dumps(list_of_events) is rejected in full - every event in the batch is
lost, and a connector that only checks the status code reports the loss as a
single line of log.

Accepted events are appended to EVENTS_PATH as JSON lines, each wrapped with
the receipt metadata a test needs: which endpoint took it, and what the raw
"time" field looked like before any coercion.

Control endpoints, none of which exist on a real HEC:

  GET  /__events   every accepted event, JSON lines
  GET  /__stats    counters, including rejections by code
  POST /__reset    clear both
  GET  /__fail     set a status code to return until reset (delivery tests)
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.getenv("HEC_TOKEN", "uat-token")
PORT = int(os.getenv("HEC_PORT", "8088"))
EVENTS_PATH = os.getenv("HEC_EVENTS", "/work/hec-events.jsonl")

_lock = threading.Lock()
_stats = {
    "requests": 0,
    "accepted_events": 0,
    "accepted_batches": 0,
    "rejected_batches": 0,
    "by_code": {},
    "bad_time_values": [],
}
_forced_status = None

DECODER = json.JSONDecoder()


def _bump(code):
    key = str(code)
    _stats["by_code"][key] = _stats["by_code"].get(key, 0) + 1


def split_objects(text):
    """Read concatenated or newline-separated JSON objects, as HEC does.

    Returns (objects, error) - error is set on the first thing that is not a
    complete JSON value, which is how a truncated or array body is caught.
    """
    objects = []
    idx, end = 0, len(text)
    while idx < end:
        while idx < end and text[idx] in " \t\r\n":
            idx += 1
        if idx >= end:
            break
        try:
            obj, idx = DECODER.raw_decode(text, idx)
        except ValueError as exc:
            return objects, f"malformed JSON at offset {idx}: {exc}"
        objects.append(obj)
    return objects, None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _reply(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _reject(self, status, text, code):
        with _lock:
            _stats["rejected_batches"] += 1
            _bump(code)
        self._reply(status, {"text": text, "code": code})

    def do_GET(self):
        if self.path == "/__events":
            with _lock:
                try:
                    with open(EVENTS_PATH, "rb") as handle:
                        body = handle.read()
                except FileNotFoundError:
                    body = b""
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/__stats":
            with _lock:
                self._reply(200, dict(_stats))
            return
        if self.path.startswith("/__fail"):
            global _forced_status
            _, _, arg = self.path.partition("=")
            _forced_status = int(arg) if arg.isdigit() else None
            self._reply(200, {"forced_status": _forced_status})
            return
        if self.path.endswith("/health"):
            self._reply(200, {"text": "HEC is healthy", "code": 17})
            return
        self._reply(404, {"text": "Not found", "code": 404})

    def do_POST(self):
        if self.path == "/__reset":
            with _lock:
                _stats.update(
                    requests=0,
                    accepted_events=0,
                    accepted_batches=0,
                    rejected_batches=0,
                    by_code={},
                    bad_time_values=[],
                )
                open(EVENTS_PATH, "w").close()
            self._reply(200, {"text": "reset"})
            return

        with _lock:
            _stats["requests"] += 1

        auth = self.headers.get("Authorization", "")
        if not auth:
            self._reject(401, "Token is required", 2)
            return
        if auth != f"Splunk {TOKEN}":
            self._reject(403, "Invalid token", 4)
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw.strip():
            self._reject(400, "No data", 5)
            return

        if _forced_status is not None:
            with _lock:
                _stats["rejected_batches"] += 1
                _bump(_forced_status)
            self._reply(_forced_status, {"text": "Forced failure", "code": 8})
            return

        text = raw.decode("utf-8", errors="replace").lstrip()

        # A JSON array is the single most common way to get this wrong, and it
        # is not a partial failure: HEC takes none of the batch.
        if text.startswith("["):
            self._reject(400, "Invalid data format", 6)
            return

        objects, err = split_objects(text)
        if err:
            self._reject(400, "Invalid data format", 6)
            return
        if not objects:
            self._reject(400, "No data", 5)
            return

        accepted = []
        for obj in objects:
            if not isinstance(obj, dict) or "event" not in obj or obj["event"] in ("", None):
                self._reject(400, "No data", 5)
                return
            raw_time = obj.get("time")
            if raw_time is not None and not isinstance(raw_time, (int, float)):
                try:
                    float(raw_time)
                except (TypeError, ValueError):
                    with _lock:
                        _stats["bad_time_values"].append(str(raw_time)[:80])
                    self._reject(400, "Invalid data format", 6)
                    return
            accepted.append(obj)

        with _lock:
            with open(EVENTS_PATH, "a") as handle:
                for obj in accepted:
                    handle.write(json.dumps({"received": obj, "endpoint": self.path}) + "\n")
            _stats["accepted_events"] += len(accepted)
            _stats["accepted_batches"] += 1
            _bump(0)

        self._reply(200, {"text": "Success", "code": 0})


def main():
    open(EVENTS_PATH, "a").close()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"mock HEC on :{PORT}, token={TOKEN!r}, events -> {EVENTS_PATH}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
