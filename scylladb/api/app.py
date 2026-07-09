"""Telemetry REST API for ScyllaDB.

Any app or frontend ingests and queries IoT/data-pipeline telemetry through
these HTTP endpoints — no direct CQL knowledge required. Structured readings and
unstructured JSON payloads share one ingest path.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from cassandra import ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
from cassandra.policies import (
    DCAwareRoundRobinPolicy,
    TokenAwarePolicy,
    ExponentialReconnectionPolicy,
)
from cassandra.query import SimpleStatement
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

CONTACT_POINTS = os.getenv("SCYLLA_CONTACT_POINTS", "127.0.0.1").split(",")
USERNAME = os.getenv("SCYLLA_USERNAME", "cassandra")
PASSWORD = os.getenv("SCYLLA_PASSWORD", "cassandra")
KEYSPACE = os.getenv("SCYLLA_KEYSPACE", "telemetry")
PORT = int(os.getenv("SCYLLA_PORT", "9042"))
LOCAL_DC = os.getenv("SCYLLA_LOCAL_DC", "datacenter1")
# LOCAL_QUORUM by default: survives a node loss without cross-DC latency.
WRITE_CL = getattr(ConsistencyLevel, os.getenv("SCYLLA_WRITE_CL", "LOCAL_QUORUM"))
READ_CL = getattr(ConsistencyLevel, os.getenv("SCYLLA_READ_CL", "LOCAL_QUORUM"))

app = FastAPI(title="ScyllaDB Telemetry API", version="1.0.0")
_session = None


def bucket_for(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d-%H")


def get_session():
    global _session
    if _session is None:
        auth = PlainTextAuthProvider(username=USERNAME, password=PASSWORD)
        # Token-aware routing sends each request straight to a replica owning the
        # partition (no coordinator hop); DC-aware keeps traffic in the local DC.
        profile = ExecutionProfile(
            load_balancing_policy=TokenAwarePolicy(
                DCAwareRoundRobinPolicy(local_dc=LOCAL_DC)
            ),
            consistency_level=READ_CL,
            request_timeout=30,
        )
        cluster = Cluster(
            CONTACT_POINTS,
            port=PORT,
            auth_provider=auth,
            protocol_version=4,
            execution_profiles={EXEC_PROFILE_DEFAULT: profile},
            reconnection_policy=ExponentialReconnectionPolicy(1.0, 60.0),
            idle_heartbeat_interval=30,
        )
        _session = cluster.connect(KEYSPACE)
    return _session


class Event(BaseModel):
    device_id: str
    metric: str
    value: Optional[float] = None
    unit: Optional[str] = None
    event_time: Optional[datetime] = None
    payload: Optional[dict[str, Any]] = None


class DeviceReg(BaseModel):
    device_id: str
    kind: str = "sensor"
    location: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health():
    try:
        get_session().execute("SELECT now() FROM system.local")
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/events")
def ingest(event: Event):
    session = get_session()
    ts = event.event_time or datetime.now(timezone.utc)
    session.execute(
        SimpleStatement(
            "INSERT INTO raw_events (device_id, bucket, event_time, event_id, "
            "metric, value, unit, payload, ingested_at) "
            "VALUES (%s, %s, %s, now(), %s, %s, %s, %s, %s)"
        ),
        (
            event.device_id, bucket_for(ts), ts, event.metric, event.value,
            event.unit, json.dumps(event.payload) if event.payload else None,
            datetime.now(timezone.utc),
        ),
    )
    session.execute(
        "UPDATE devices SET last_seen = %s WHERE device_id = %s",
        (ts, event.device_id),
    )
    return {"ingested": True, "device_id": event.device_id, "bucket": bucket_for(ts)}


@app.post("/events/bulk")
def ingest_bulk(events: list[Event]):
    session = get_session()
    insert = session.prepare(
        "INSERT INTO raw_events (device_id, bucket, event_time, event_id, "
        "metric, value, unit, payload, ingested_at) "
        "VALUES (?, ?, ?, now(), ?, ?, ?, ?, ?)"
    )
    from cassandra.concurrent import execute_concurrent_with_args

    now = datetime.now(timezone.utc)
    params = []
    seen_devices = set()
    for e in events:
        ts = e.event_time or now
        params.append((
            e.device_id, bucket_for(ts), ts, e.metric, e.value, e.unit,
            json.dumps(e.payload) if e.payload else None, now,
        ))
        seen_devices.add(e.device_id)
    execute_concurrent_with_args(session, insert, params, concurrency=64)
    return {"ingested": len(params), "devices": len(seen_devices)}


@app.get("/events/{device_id}/count")
def count_events(device_id: str, bucket: Optional[str] = None):
    session = get_session()
    bkt = bucket or bucket_for(datetime.now(timezone.utc))
    row = session.execute(
        "SELECT COUNT(*) AS c FROM raw_events WHERE device_id=%s AND bucket=%s",
        (device_id, bkt),
    ).one()
    return {"device_id": device_id, "bucket": bkt, "count": row.c}


@app.get("/events/{device_id}")
def query_events(device_id: str, bucket: Optional[str] = None, limit: int = 100):
    session = get_session()
    bkt = bucket or bucket_for(datetime.now(timezone.utc))
    rows = session.execute(
        "SELECT device_id, event_time, metric, value, unit, payload "
        "FROM raw_events WHERE device_id=%s AND bucket=%s LIMIT %s",
        (device_id, bkt, limit),
    )
    return {
        "device_id": device_id,
        "bucket": bkt,
        "events": [
            {
                "event_time": r.event_time.isoformat() if r.event_time else None,
                "metric": r.metric,
                "value": r.value,
                "unit": r.unit,
                "payload": json.loads(r.payload) if r.payload else None,
            }
            for r in rows
        ],
    }


@app.get("/metrics/{device_id}/{metric}")
def query_rollup(device_id: str, metric: str, bucket: Optional[str] = None, limit: int = 60):
    session = get_session()
    bkt = bucket or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = session.execute(
        "SELECT minute, count, sum, min, max, avg FROM metrics_1m "
        "WHERE device_id=%s AND metric=%s AND bucket=%s LIMIT %s",
        (device_id, metric, bkt, limit),
    )
    return {
        "device_id": device_id,
        "metric": metric,
        "bucket": bkt,
        "points": [
            {
                "minute": r.minute.isoformat() if r.minute else None,
                "count": r.count, "sum": r.sum, "min": r.min, "max": r.max, "avg": r.avg,
            }
            for r in rows
        ],
    }


@app.post("/devices")
def register_device(dev: DeviceReg):
    session = get_session()
    now = datetime.now(timezone.utc)
    session.execute(
        "INSERT INTO devices (device_id, kind, location, metadata, registered_at, last_seen) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (dev.device_id, dev.kind, dev.location, json.dumps(dev.metadata), now, now),
    )
    return {"registered": dev.device_id}


@app.get("/devices")
def list_devices(limit: int = 100):
    session = get_session()
    rows = session.execute(SimpleStatement(f"SELECT device_id, kind, location, last_seen FROM devices LIMIT {int(limit)}"))
    return {
        "devices": [
            {
                "device_id": r.device_id, "kind": r.kind, "location": r.location,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
            }
            for r in rows
        ]
    }
