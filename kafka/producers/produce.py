#!/usr/bin/env python3
"""
Config-driven Kafka event producer.

Emits JSON events for a named scenario (see scenarios.yaml) to a Kafka topic --
different applications, different data, one producer. The `telemetry` scenario
feeds the Kafka -> Flink -> Cassandra integration demo.

    python3 produce.py --scenario telemetry --bootstrap localhost:19092 --rate 1000 --count 100000
    python3 produce.py --scenario orders --bootstrap localhost:19092

Needs: kafka-python (+ pyyaml). No Faker dependency -- generators use the stdlib.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

SENSORS = [f"sensor-{i:03d}" for i in range(1, 25)]
METRICS = ["temperature_c", "humidity_pct", "vibration_mm_s", "power_w"]
TOPPINGS = ["pepperoni", "mushroom", "olive", "onion", "pineapple", "basil"]
PAGES = [f"/p/{p}" for p in ("home", "search", "cart", "checkout", "product", "profile")]
SYMBOLS = ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA", "TSLA"]


def telemetry() -> tuple[str, dict]:
    sensor = random.choice(SENSORS)
    metric = random.choice(METRICS)
    base = {"temperature_c": 22, "humidity_pct": 45, "vibration_mm_s": 2, "power_w": 120}[metric]
    value = round(random.gauss(base, base * 0.15), 3)
    if random.random() < 0.01:          # 1% outliers, for the anomaly path
        value = round(base * random.uniform(3, 6), 3)
    return sensor, {
        "sensor_id": sensor, "metric": metric, "value": value,
        "event_time": datetime.now(timezone.utc).isoformat(),
    }


def pizza_order() -> tuple[str, dict]:
    oid = f"ord-{random.randint(1, 10**9)}"
    return oid, {
        "order_id": oid,
        "shop_id": random.randint(1, 12),
        "count": random.randint(1, 10),
        "toppings": random.sample(TOPPINGS, k=random.randint(1, 4)),
        "amount": round(random.uniform(8, 90), 2),
        "event_time": datetime.now(timezone.utc).isoformat(),
    }


def user_click() -> tuple[str, dict]:
    sid = f"sess-{random.randint(1, 100000)}"
    return sid, {
        "session_id": sid,
        "user_id": random.randint(1, 5000),
        "page": random.choice(PAGES),
        "latency_ms": round(random.uniform(5, 800), 1),
        "event_time": datetime.now(timezone.utc).isoformat(),
    }


def stock_tick() -> tuple[str, dict]:
    sym = random.choice(SYMBOLS)
    return sym, {
        "symbol": sym,
        "price": round(random.uniform(50, 900), 2),
        "volume": random.randint(100, 100000),
        "event_time": datetime.now(timezone.utc).isoformat(),
    }


GENERATORS = {
    "telemetry": telemetry, "pizza_order": pizza_order,
    "user_click": user_click, "stock_tick": stock_tick,
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Config-driven Kafka event producer")
    ap.add_argument("--scenario", default="telemetry")
    ap.add_argument("--bootstrap", default="localhost:19092")
    ap.add_argument("--config", default=str(Path(__file__).with_name("scenarios.yaml")))
    ap.add_argument("--rate", type=float, default=1000.0, help="events/sec")
    ap.add_argument("--count", type=int, default=-1, help="events to send (-1 = forever)")
    args = ap.parse_args()

    from kafka import KafkaProducer  # imported here so the generators stay import-light

    scenarios = yaml.safe_load(open(args.config))["scenarios"]
    if args.scenario not in scenarios:
        raise SystemExit(f"unknown scenario '{args.scenario}'; have {list(scenarios)}")
    spec = scenarios[args.scenario]
    gen = GENERATORS[spec["generator"]]
    topic = spec["topic"]

    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap.split(","),
        value_serializer=lambda v: json.dumps(v).encode(),
        key_serializer=lambda k: k.encode(),
        acks="all", linger_ms=20,
    )
    print(f"producing scenario={args.scenario} -> topic={topic} @ {args.rate}/s")
    sleep = 1.0 / args.rate if args.rate > 0 else 0
    sent = 0
    try:
        while args.count < 0 or sent < args.count:
            key, event = gen()
            producer.send(topic, key=key, value=event)
            sent += 1
            if sent % 5000 == 0:
                print(f"  sent {sent}")
            if sleep:
                time.sleep(sleep)
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush()
        print(f"done: {sent} events to {topic}")


if __name__ == "__main__":
    main()
