"""ETL worker: rolls raw telemetry events into structured per-minute aggregates.

Periodically scans recent raw_events, computes count/sum/min/max/avg per
device+metric+minute, and upserts into metrics_1m so apps/dashboards read cheap
downsampled series instead of raw high-rate data. Unparseable rows are routed to
the dead_letter table rather than dropped.
"""
import os
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

CONTACT_POINTS = os.getenv("SCYLLA_CONTACT_POINTS", "127.0.0.1").split(",")
USERNAME = os.getenv("SCYLLA_USERNAME", "cassandra")
PASSWORD = os.getenv("SCYLLA_PASSWORD", "cassandra")
KEYSPACE = os.getenv("SCYLLA_KEYSPACE", "telemetry")
PORT = int(os.getenv("SCYLLA_PORT", "9042"))
INTERVAL = int(os.getenv("ETL_INTERVAL_SECONDS", "60"))

_running = True


def _stop(*_):
    global _running
    _running = False


def connect():
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.cluster import Cluster
    auth = PlainTextAuthProvider(username=USERNAME, password=PASSWORD)
    return Cluster(CONTACT_POINTS, port=PORT, auth_provider=auth).connect(KEYSPACE)


def minute_floor(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


def rollup_once(session) -> int:
    """Aggregate the current hour bucket's raw events into metrics_1m.

    Returns the number of (device, metric, minute) aggregate rows written.
    """
    now = datetime.now(timezone.utc)
    bucket = now.strftime("%Y-%m-%d-%H")
    day = now.strftime("%Y-%m-%d")

    rows = session.execute(
        "SELECT device_id, metric, value, event_time, payload FROM raw_events "
        "WHERE bucket=%s ALLOW FILTERING",
        (bucket,),
    )

    agg = defaultdict(lambda: {"count": 0, "sum": 0.0, "min": None, "max": None})
    for r in rows:
        if r.value is None:
            # Unparseable/structured-value-less event → dead letter, keep the body.
            session.execute(
                "INSERT INTO dead_letter (device_id, bucket, event_time, event_id, reason, payload) "
                "VALUES (%s, %s, %s, now(), %s, %s)",
                (r.device_id, bucket, r.event_time, "missing numeric value", r.payload),
            )
            continue
        key = (r.device_id, r.metric, minute_floor(r.event_time))
        a = agg[key]
        a["count"] += 1
        a["sum"] += r.value
        a["min"] = r.value if a["min"] is None else min(a["min"], r.value)
        a["max"] = r.value if a["max"] is None else max(a["max"], r.value)

    written = 0
    for (device_id, metric, minute), a in agg.items():
        avg = a["sum"] / a["count"] if a["count"] else 0.0
        session.execute(
            "INSERT INTO metrics_1m (device_id, metric, bucket, minute, count, sum, min, max, avg) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (device_id, metric, day, minute, a["count"], a["sum"], a["min"], a["max"], avg),
        )
        written += 1
    return written


def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    session = connect()
    print(f"ETL worker started; interval={INTERVAL}s", flush=True)
    while _running:
        try:
            n = rollup_once(session)
            print(f"rollup wrote {n} aggregate rows", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"rollup error: {exc}", file=sys.stderr, flush=True)
        for _ in range(INTERVAL):
            if not _running:
                break
            time.sleep(1)
    print("ETL worker stopped", flush=True)


if __name__ == "__main__":
    main()
