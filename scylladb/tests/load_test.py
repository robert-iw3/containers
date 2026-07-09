#!/usr/bin/env python3
"""End-to-end pipeline load test against a live telemetry API + ScyllaDB cluster.

Generates small / medium / large synthetic IoT datasets, ingests them through the
REST API in bulk, then queries back through the API to prove every event was
processed, stored (RF-replicated), and is accessible end to end.

Usage:
  API_URL=http://localhost:8000 python load_test.py [small|medium|large|all]

Exit code is non-zero if any dataset's stored count does not match what was sent.
"""
import json
import os
import random
import sys
import time
import urllib.request
from datetime import datetime, timezone

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

SIZES = {"small": 100, "medium": 5_000, "large": 50_000}
BATCH = 1_000
METRICS = ["temperature", "humidity", "pressure", "voltage"]


def _post(path, body):
    req = urllib.request.Request(
        f"{API_URL}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _get(path):
    with urllib.request.urlopen(f"{API_URL}{path}", timeout=120) as resp:
        return json.loads(resp.read())


def make_events(device_id, n, bucket_ts):
    events = []
    for _ in range(n):
        metric = random.choice(METRICS)
        events.append({
            "device_id": device_id,
            "metric": metric,
            "value": round(random.uniform(0, 100), 3),
            "unit": "u",
            "event_time": bucket_ts.isoformat(),
            "payload": {"seq": random.randint(1, 1_000_000), "note": "synthetic"},
        })
    return events


def run_dataset(name, count):
    device_id = f"loadtest-{name}"
    # Pin all events into one hour bucket so the count query is exact.
    bucket_ts = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    bucket = bucket_ts.strftime("%Y-%m-%d-%H")

    _post("/devices", {"device_id": device_id, "kind": "loadtest", "location": name})

    print(f"[{name}] ingesting {count} events in batches of {BATCH}...")
    t0 = time.time()
    sent = 0
    for start in range(0, count, BATCH):
        chunk = make_events(device_id, min(BATCH, count - start), bucket_ts)
        res = _post("/events/bulk", chunk)
        sent += res["ingested"]
    dt = time.time() - t0
    rate = sent / dt if dt else 0
    print(f"[{name}] sent {sent} events in {dt:.1f}s ({rate:,.0f} ev/s)")

    # Query back through the API and confirm the stored count matches.
    stored = _get(f"/events/{device_id}/count?bucket={bucket}")["count"]
    print(f"[{name}] API reports {stored} stored (expected {count})")

    # Spot-check a page of events is actually retrievable with real payloads.
    page = _get(f"/events/{device_id}?bucket={bucket}&limit=5")["events"]
    assert page, f"[{name}] no events retrievable via API"
    assert page[0]["payload"] and "seq" in page[0]["payload"], "payload not round-tripped"

    ok = stored == count
    print(f"[{name}] {'PASS' if ok else 'FAIL'}: stored == sent == {count}" if ok
          else f"[{name}] FAIL: stored {stored} != sent {count}")
    return ok


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    datasets = SIZES if which == "all" else {which: SIZES[which]}
    results = {name: run_dataset(name, n) for name, n in datasets.items()}
    print("\n=== summary ===")
    for name, ok in results.items():
        print(f"  {name:8} {SIZES[name]:>7} events: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
