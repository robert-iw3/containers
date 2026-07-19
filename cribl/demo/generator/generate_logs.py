"""
Synthetic log generator for the Cribl demo. Stdlib only.

Streams three realistic log shapes over syslog TCP (RFC3164 framing):
  web01  nginx   - combined access-log lines
  app01  orders  - JSON application events (info/warn/error/debug,
                   some with customer emails - the pipeline masks them)
  auth01 sshd    - auth success/failure lines

The debug JSON events and the emails exist on purpose: the demo pipeline
must drop the former and redact the latter, and the smoke test asserts
both.
"""

import argparse
import json
import random
import socket
import time
from datetime import datetime, timezone

PATHS = ["/", "/api/orders", "/api/cart", "/login", "/static/app.js", "/checkout"]
METHODS = ["GET", "GET", "GET", "POST", "PUT"]
STATUSES = [200, 200, 200, 200, 201, 301, 404, 500]
LEVELS = ["info", "info", "info", "warn", "error", "debug", "debug"]
USERS = ["ana", "bob", "chen", "dara", "eli"]
ACTIONS = ["order.created", "order.paid", "cart.updated", "payment.retried"]


def now_syslog():
    return datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")


def access_line(rng):
    ip = f"10.0.{rng.randint(0, 20)}.{rng.randint(1, 250)}"
    return (
        f'{ip} - - [{datetime.now(timezone.utc).strftime("%d/%b/%Y:%H:%M:%S +0000")}] '
        f'"{rng.choice(METHODS)} {rng.choice(PATHS)} HTTP/1.1" '
        f"{rng.choice(STATUSES)} {rng.randint(120, 50000)}"
    )


def app_event(rng):
    user = rng.choice(USERS)
    return json.dumps(
        {
            "level": rng.choice(LEVELS),
            "action": rng.choice(ACTIONS),
            "order_id": rng.randint(10000, 99999),
            "user_email": f"{user}@example.com",
            "latency_ms": rng.randint(3, 900),
        }
    )


def auth_line(rng):
    user = rng.choice(USERS + ["root", "admin"])
    ip = f"203.0.113.{rng.randint(1, 250)}"
    if rng.random() < 0.3:
        return f"Failed password for invalid user {user} from {ip} port {rng.randint(1024, 65000)} ssh2"
    return f"Accepted publickey for {user} from {ip} port {rng.randint(1024, 65000)} ssh2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="cribl-demo")
    ap.add_argument("--port", type=int, default=5140)
    ap.add_argument("--rate", type=float, default=20, help="events per second")
    ap.add_argument("--count", type=int, default=0, help="stop after N events (0 = forever)")
    args = ap.parse_args()

    rng = random.Random(42)
    sent = 0
    sock = None
    while args.count == 0 or sent < args.count:
        try:
            if sock is None:
                sock = socket.create_connection((args.host, args.port), timeout=10)
                print(f"connected to {args.host}:{args.port}", flush=True)
            pick = rng.random()
            if pick < 0.45:
                msg = f"<134>{now_syslog()} web01 nginx: {access_line(rng)}"
            elif pick < 0.8:
                msg = f"<134>{now_syslog()} app01 orders: {app_event(rng)}"
            else:
                msg = f"<38>{now_syslog()} auth01 sshd[{rng.randint(100, 9999)}]: {auth_line(rng)}"
            sock.sendall(msg.encode() + b"\n")
            sent += 1
            if sent % 500 == 0:
                print(f"sent {sent} events", flush=True)
            time.sleep(1.0 / args.rate)
        except OSError as exc:
            print(f"connection lost ({exc}); retrying in 3s", flush=True)
            if sock is not None:
                sock.close()
                sock = None
            time.sleep(3)
    print(f"done: sent {sent} events", flush=True)


if __name__ == "__main__":
    main()
