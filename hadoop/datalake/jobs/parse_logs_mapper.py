#!/usr/bin/env python3
"""Hadoop Streaming mapper: parse heterogeneous / unstructured log lines into a
common (source, level) key and emit `source::level\t1` for aggregation.

Handles four formats in one pass -- JSON app logs, Apache combined access logs,
CSV, and syslog -- turning unstructured multi-format logs into structured events,
the core of a datalake "raw -> curated" step. Reads stdin, writes stdout (the
Streaming contract), so it runs distributed across the YARN NodeManagers.
"""

import json
import re
import sys

APACHE = re.compile(r'^(\S+) \S+ \S+ \[[^\]]+\] "(\S+) (\S+)[^"]*" (\d{3})')
SYSLOG = re.compile(r'^(?:<\d+>)?[A-Z][a-z]{2}\s+\d+\s+[\d:]+\s+(\S+)\s+(\S+?)(?:\[\d+\])?:')
ISO = re.compile(r'^\d{4}-\d\d-\d\d')


def level_from_status(code: str) -> str:
    c = int(code)
    if c >= 500:
        return "ERROR"
    if c >= 400:
        return "WARN"
    return "INFO"


def classify(line: str) -> tuple[str, str]:
    s = line.strip()
    if not s:
        return None
    # JSON application log
    if s.startswith("{"):
        try:
            o = json.loads(s)
            return (str(o.get("service") or o.get("source") or "app"),
                    str(o.get("level", "INFO")).upper())
        except ValueError:
            pass
    # Apache combined access log
    m = APACHE.match(s)
    if m:
        return ("web", level_from_status(m.group(4)))
    # CSV: ts,level,source,message
    if ISO.match(s) and s.count(",") >= 3:
        parts = s.split(",", 3)
        return (parts[2].strip(), parts[1].strip().upper())
    # Syslog
    m = SYSLOG.match(s)
    if m:
        bad = any(w in s.lower() for w in ("fail", "killed", "error", "out of memory"))
        return (m.group(2), "ERROR" if bad else "INFO")
    return ("unknown", "UNKNOWN")


def main() -> None:
    for line in sys.stdin:
        res = classify(line.rstrip("\n"))
        if res:
            source, level = res
            sys.stdout.write(f"{source}::{level}\t1\n")


if __name__ == "__main__":
    main()
