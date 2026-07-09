import json
import os
import random
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer

BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:19092")
TOPIC = os.environ.get("KAFKA_TOPIC", "app-logs")
RATE_PER_SEC = float(os.environ.get("LOG_RATE_PER_SEC", "20"))
SERVICE_NAMES = os.environ.get(
    "SERVICE_NAMES", "checkout,inventory,payments,shipping,auth,search"
).split(",")
HOSTS = [f"host-{i:02d}" for i in range(1, 9)]
ERROR_MESSAGES = [
    "connection timeout to downstream service",
    "unhandled exception in request handler",
    "database deadlock detected",
    "rate limit exceeded",
    "invalid authentication token",
    "upstream returned 503",
]
INFO_MESSAGES = [
    "request completed",
    "cache hit",
    "cache miss, fetched from source",
    "background job finished",
    "health check ok",
]
WARN_MESSAGES = [
    "retrying request after transient failure",
    "response latency above threshold",
    "connection pool nearing capacity",
]

LEVEL_WEIGHTS = [("INFO", 0.75), ("WARN", 0.15), ("ERROR", 0.08), ("DEBUG", 0.02)]


def pick_level():
    r = random.random()
    cumulative = 0.0
    for level, weight in LEVEL_WEIGHTS:
        cumulative += weight
        if r <= cumulative:
            return level
    return "INFO"


def message_for(level):
    if level == "ERROR":
        return random.choice(ERROR_MESSAGES)
    if level == "WARN":
        return random.choice(WARN_MESSAGES)
    return random.choice(INFO_MESSAGES)


def build_event():
    level = pick_level()
    status_code = (
        random.choice([500, 502, 503, 504])
        if level == "ERROR"
        else random.choice([200, 200, 200, 201, 204, 301, 404])
    )
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": str(uuid.uuid4()),
        "service": random.choice(SERVICE_NAMES),
        "host": random.choice(HOSTS),
        "level": level,
        "message": message_for(level),
        "status_code": status_code,
        "duration_ms": round(random.gammavariate(2.0, 40.0), 2),
    }


def delivery_callback(err, msg):
    if err is not None:
        print(f"delivery failed: {err}")


def main():
    producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})
    interval = 1.0 / RATE_PER_SEC if RATE_PER_SEC > 0 else 0.05
    while True:
        event = build_event()
        producer.produce(
            TOPIC,
            key=event["service"].encode("utf-8"),
            value=json.dumps(event).encode("utf-8"),
            callback=delivery_callback,
        )
        producer.poll(0)
        time.sleep(interval)


if __name__ == "__main__":
    main()
