"""
Prove the mock HEC rejects what it claims to reject.

A receiver is only useful as a test oracle if it fails the bad cases, so each
case below asserts a specific status and code. If this file ever reports a
rejection case as accepted, the oracle tests nothing and every downstream
result is void.

    python3 selftest_hec.py [base_url] [token]
"""

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else "uat-token"
URL = f"{BASE}/services/collector/event"

PASS, FAIL = 0, 0


def post(body, token=TOKEN, headers=True):
    data = body if isinstance(body, bytes) else body.encode()
    req = urllib.request.Request(URL, data=data, method="POST")
    if headers:
        req.add_header("Authorization", f"Splunk {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}: got {got}, want {want}")


def main():
    urllib.request.urlopen(
        urllib.request.Request(f"{BASE}/__reset", data=b"", method="POST"), timeout=10
    )

    one = json.dumps({"event": {"a": 1}, "sourcetype": "t"})

    print("mock HEC self-test")
    check("single object accepted", post(one), (200, {"text": "Success", "code": 0}))
    check(
        "two objects newline-separated accepted",
        post(one + "\n" + one),
        (200, {"text": "Success", "code": 0}),
    )
    check(
        "two objects concatenated accepted",
        post(one + one),
        (200, {"text": "Success", "code": 0}),
    )
    check(
        "numeric time accepted",
        post(json.dumps({"event": {"a": 1}, "time": 1767225600})),
        (200, {"text": "Success", "code": 0}),
    )
    check(
        "numeric string time accepted",
        post(json.dumps({"event": {"a": 1}, "time": "1767225600.5"})),
        (200, {"text": "Success", "code": 0}),
    )

    # The rejections. Each of these is a defect a permissive receiver hides.
    check(
        "JSON ARRAY rejected",
        post(json.dumps([{"event": {"a": 1}}, {"event": {"a": 2}}])),
        (400, {"text": "Invalid data format", "code": 6}),
    )
    check(
        "object without event key rejected",
        post(json.dumps({"sourcetype": "t", "fields": {"a": 1}})),
        (400, {"text": "No data", "code": 5}),
    )
    check(
        "empty event value rejected",
        post(json.dumps({"event": ""})),
        (400, {"text": "No data", "code": 5}),
    )
    check(
        "non-numeric time rejected",
        post(json.dumps({"event": {"a": 1}, "time": "2026-09-07T12:00:00Z"})),
        (400, {"text": "Invalid data format", "code": 6}),
    )
    check("empty body rejected", post(""), (400, {"text": "No data", "code": 5}))
    check(
        "truncated JSON rejected",
        post('{"event": {"a": 1}'),
        (400, {"text": "Invalid data format", "code": 6}),
    )
    check(
        "missing token rejected",
        post(one, headers=False),
        (401, {"text": "Token is required", "code": 2}),
    )
    check(
        "wrong token rejected",
        post(one, token="not-the-token"),
        (403, {"text": "Invalid token", "code": 4}),
    )

    # Only the accepted cases should have been stored.
    with urllib.request.urlopen(f"{BASE}/__stats", timeout=10) as resp:
        stats = json.loads(resp.read())
    # 1 single + 2 newline-separated + 2 concatenated + 2 timestamped.
    check("accepted event count", stats["accepted_events"], 7)
    check("rejected batch count", stats["rejected_batches"], 8)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
