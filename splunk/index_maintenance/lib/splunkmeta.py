"""Read Splunk's own bucket metadata, without credentials.

Every bucket carries Hosts.data, Sources.data and SourceTypes.data: tab
separated, one line per value, holding the number of events and the earliest
and latest event time. Splunk maintains them for its own metadata searches.

Reading them answers "what data is actually here, and when did it last
arrive" on an instance nobody has the password for -- which is the position
someone is in on their first day.

The format, per line:

    id <tab> namespace::value <tab> count <tab> earliest <tab> latest <tab> last_indextime

The first line is a totals row with no namespace prefix, and is skipped.
"""
from __future__ import annotations

import subprocess
from typing import Dict, List, Optional, Tuple


class Target:
    """Where Splunk is, and how to run a command against it."""

    def __init__(self, container: Optional[str], splunk_home: str,
                 user: Optional[str] = None):
        self.container = container
        self.home = splunk_home.rstrip("/")
        self.user = user or self._resolve_user()

    def _resolve_user(self) -> str:
        if not self.container:
            return ""
        out = self._raw(["podman", "exec", self.container, "stat", "-c", "%U",
                         f"{self.home}/etc"])
        return out.strip() or "splunk"

    @staticmethod
    def _raw(cmd: List[str]) -> str:
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p.stdout

    def sh(self, command: str) -> str:
        if self.container:
            cmd = ["podman", "exec"]
            if self.user:
                cmd += ["-u", self.user]
            cmd += [self.container, "sh", "-c", command]
        else:
            cmd = ["sh", "-c", command]
        return self._raw(cmd)

    def splunk(self, args: str) -> str:
        out = self.sh(f"{self.home}/bin/splunk {args} 2>/dev/null")
        return "\n".join(l for l in out.splitlines()
                         if "Server Certificate Hostname Validation" not in l)


def indexes(t: Target) -> List[str]:
    """Every index the merged configuration defines."""
    out = t.splunk("btool indexes list")
    names = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            n = line[1:-1]
            if n != "default" and ":" not in n:
                names.append(n)
    return sorted(set(names))


def index_settings(t: Target, index: str) -> Dict[str, str]:
    out = t.splunk(f"btool indexes list '{index}'")
    settings = {}
    for line in out.splitlines():
        if "=" in line and not line.strip().startswith("["):
            k, _, v = line.partition("=")
            settings[k.strip()] = v.strip()
    return settings


def index_dirs(t: Target, index: str, settings: Dict[str, str]) -> Tuple[str, str]:
    home = settings.get("homePath", "")
    cold = settings.get("coldPath", "")
    db = f"{t.home}/var/lib/splunk"
    for frm, to in (("$SPLUNK_DB", db), ("$SPLUNK_HOME", t.home)):
        home = home.replace(frm, to)
        cold = cold.replace(frm, to)
    return home, cold


# A metadata row, aggregated across every bucket of an index.
class Row:
    __slots__ = ("value", "count", "earliest", "latest", "last_index")

    def __init__(self, value: str):
        self.value = value
        self.count = 0
        self.earliest = None
        self.latest = None
        self.last_index = None

    def add(self, count: int, earliest: int, latest: int, last_index: int):
        self.count += count
        if earliest and (self.earliest is None or earliest < self.earliest):
            self.earliest = earliest
        if latest and (self.latest is None or latest > self.latest):
            self.latest = latest
        if last_index and (self.last_index is None or last_index > self.last_index):
            self.last_index = last_index


def _parse(text: str, prefix: str) -> List[Tuple[str, int, int, int, int]]:
    rows = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        name = parts[1].strip()
        if not name.startswith(prefix):
            continue  # the totals row carries no namespace
        def num(x):
            x = x.strip()
            return int(x) if x.isdigit() else 0
        rows.append((name[len(prefix):], num(parts[2]), num(parts[3]),
                     num(parts[4]), num(parts[5])))
    return rows


def metadata(t: Target, index: str, settings: Dict[str, str],
             kind: str = "sourcetype") -> Dict[str, Row]:
    """Aggregate one metadata kind across every bucket of an index.

    kind is 'sourcetype', 'host' or 'source'.
    """
    filename = {"sourcetype": "SourceTypes.data",
                "host": "Hosts.data",
                "source": "Sources.data"}[kind]
    prefix = f"{kind}::"
    home, cold = index_dirs(t, index, settings)
    paths = " ".join(f"'{d}'/*/{filename}" for d in (home, cold) if d)
    # One cat for every bucket at once: an index can hold hundreds, and a
    # command per bucket turns a report into a wait.
    text = t.sh(f"cat {paths} 2>/dev/null")
    out: Dict[str, Row] = {}
    for name, count, early, late, li in _parse(text, prefix):
        row = out.setdefault(name, Row(name))
        row.add(count, early, late, li)
    return out


def disk_free(t: Target, path: str) -> Tuple[int, int, int]:
    """(used_kb, avail_kb, percent_used) for the filesystem holding path."""
    out = t.sh(f"df -Pk '{path}' 2>/dev/null | sed -n 2p")
    parts = out.split()
    if len(parts) >= 5:
        try:
            return int(parts[2]), int(parts[3]), int(parts[4].rstrip("%"))
        except ValueError:
            pass
    return 0, 0, 0


def du_kb(t: Target, path: str) -> int:
    out = t.sh(f"du -sk '{path}' 2>/dev/null | cut -f1")
    out = out.strip().split("\t")[0].strip()
    return int(out) if out.isdigit() else 0
