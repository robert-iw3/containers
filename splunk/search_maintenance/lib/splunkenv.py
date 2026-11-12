"""Talk to a Splunk installation, and read what its scheduler has been doing.

Self-contained on purpose: these scripts get copied onto a search head on
their own, and an ops script that needs a sibling directory to import is an
ops script that does not run when it is needed.
"""
from __future__ import annotations

import re
import subprocess
from typing import Dict, Iterable, List, Optional, Tuple


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
        return subprocess.run(cmd, capture_output=True, text=True).stdout

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


# ----------------------------------------------------------------- config

class SavedSearch:
    """One saved search, as the merged configuration actually defines it."""

    __slots__ = ("name", "app", "file", "settings")

    def __init__(self, name: str, app: str, file: str, settings: Dict[str, str]):
        self.name = name
        self.app = app
        self.file = file
        self.settings = settings

    def get(self, key: str, default: str = "") -> str:
        return self.settings.get(key, default)

    @property
    def scheduled(self) -> bool:
        return (self.get("enableSched", "0").lower() in ("1", "true")
                and self.get("disabled", "0").lower() not in ("1", "true"))

    @property
    def cron(self) -> str:
        return self.get("cron_schedule", "")

    @property
    def summary_index(self) -> str:
        if self.get("action.summary_index", "0").lower() not in ("1", "true"):
            return ""
        return self.get("action.summary_index._name", "summary")

    def __repr__(self):
        return f"<SavedSearch {self.app}/{self.name}>"


def saved_searches(t: Target) -> List[SavedSearch]:
    """Every saved search, with the file each one comes from.

    btool --debug prefixes every line with its source file, which is the only
    reliable answer to "where is this set".
    """
    out = t.splunk("btool savedsearches list --debug")
    found: List[SavedSearch] = []
    name = path = None
    settings: Dict[str, str] = {}

    def flush():
        if name is not None:
            app = "system"
            m = re.search(r"/etc/apps/([^/]+)/", path or "")
            if m:
                app = m.group(1)
            elif "/etc/users/" in (path or ""):
                m2 = re.search(r"/etc/users/([^/]+)/([^/]+)/", path or "")
                app = f"user:{m2.group(1)}" if m2 else "user"
            found.append(SavedSearch(name, app, path or "?", dict(settings)))

    for line in out.splitlines():
        m = re.match(r"^(\S+)\s+\[(.+)\]\s*$", line)
        if m:
            flush()
            path, name = m.group(1), m.group(2)
            settings = {}
            continue
        m = re.match(r"^(\S+)\s+(\S+)\s*=\s*(.*)$", line)
        if m and name is not None:
            settings[m.group(2)] = m.group(3).strip()
    flush()
    return [s for s in found if s.name != "default"]


# ----------------------------------------------------------- cron handling

def cron_minutes(cron: str) -> Optional[List[int]]:
    """Which minutes of the hour this cron fires on, or None if it is not
    a shape we can reason about.

    Only the minute and hour fields matter for load: two searches collide
    when they share a minute.
    """
    parts = cron.split()
    if len(parts) < 5:
        return None
    minute = parts[0]
    if minute == "*":
        return list(range(60))
    if minute.startswith("*/"):
        try:
            step = int(minute[2:])
        except ValueError:
            return None
        return list(range(0, 60, step)) if step > 0 else None
    out = []
    for piece in minute.split(","):
        if "-" in piece:
            try:
                a, b = (int(x) for x in piece.split("-", 1))
            except ValueError:
                return None
            out.extend(range(a, min(b, 59) + 1))
        else:
            try:
                out.append(int(piece))
            except ValueError:
                return None
    return sorted(set(out)) or None


def cron_period_minutes(cron: str) -> Optional[int]:
    """How often this cron fires, in minutes, when that is a single number."""
    mins = cron_minutes(cron)
    if not mins:
        return None
    parts = cron.split()
    hour = parts[1] if len(parts) > 1 else "*"
    if hour == "*":
        if len(mins) == 1:
            return 60
        gaps = {(mins[(i + 1) % len(mins)] - m) % 60 for i, m in enumerate(mins)}
        return min(gaps) if len(gaps) == 1 else min(gaps)
    if hour.startswith("*/"):
        try:
            return int(hour[2:]) * 60
        except ValueError:
            return None
    if hour.isdigit() and len(mins) == 1:
        return 1440
    return None


_RELATIVE = re.compile(r"^-(\d+)(s|m|h|d|w|mon)(@\w+)?$")
_UNIT_MIN = {"s": 1 / 60.0, "m": 1, "h": 60, "d": 1440, "w": 10080, "mon": 43200}


def window_minutes(earliest: str) -> Optional[float]:
    """How far back a relative dispatch window reaches, in minutes."""
    e = (earliest or "").strip()
    if not e:
        return None
    m = _RELATIVE.match(e)
    if not m:
        return None
    return int(m.group(1)) * _UNIT_MIN[m.group(2)]


# ------------------------------------------------------- scheduler history

class Run:
    __slots__ = ("name", "app", "status", "reason", "run_time", "results",
                 "skew", "when", "scheduled_at")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


def scheduler_runs(t: Target, lines: int = 20000) -> List[Run]:
    """Parse the scheduler's own log. This is what actually happened, as
    opposed to what the configuration says should happen."""
    log = t.sh(f"tail -n {lines} {t.home}/var/log/splunk/scheduler.log 2>/dev/null")
    runs: List[Run] = []
    for line in log.splitlines():
        if "savedsearch_name=" not in line:
            continue
        def g(pat, cast=str, default=None):
            m = re.search(pat, line)
            if not m:
                return default
            try:
                return cast(m.group(1))
            except (TypeError, ValueError):
                return default
        runs.append(Run(
            name=g(r'savedsearch_name="([^"]*)"'),
            app=g(r'\bapp="([^"]*)"'),
            status=g(r"\bstatus=(\w+)"),
            reason=g(r'\breason="([^"]*)"'),
            run_time=g(r"\brun_time=([0-9.]+)", float),
            results=g(r"\bresult_count=(\d+)", int),
            skew=g(r"\bskew_seconds=(\d+)", int),
            when=g(r"^(\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})"),
            scheduled_at=g(r"\bscheduled_time=(\d+)"),
        ))
    return runs


def collapse_waits(runs: List[Run]) -> List[Run]:
    """One entry per attempt, not one per second spent waiting.

    A held-back search is logged again every second until it starts, so a
    search that waited three seconds writes three 'continued' lines. Counting
    those lines makes a brief queue look like a crisis: 210 lines for a
    handful of searches that each waited a moment. Collapsing on the search
    and the time it was scheduled for gives one entry per held-back attempt,
    which is the thing worth counting.
    """
    out, seen = [], set()
    for r in runs:
        if r.status == "continued":
            key = (r.name, r.scheduled_at)
            if key in seen:
                continue
            seen.add(key)
        out.append(r)
    return out


def concurrency_limit(t: Target) -> Optional[int]:
    """What the scheduler says its own limit is.

    Read, not computed. The formula from cpu count gives a number that is
    often not the number being enforced, and the enforced one is the only
    one that matters.
    """
    # Three different limits share this field name: the jobs one saved
    # search may run at once, the instance-wide ceiling on scheduled
    # searches, and a wider historical-search ceiling. Only the second
    # governs how many of an app's searches run together, and the reason
    # text is what tells them apart. Taking the last line regardless
    # returns whichever was written most recently.
    out = t.sh("grep -h 'concurrent historical scheduled searches' "
               f"{t.home}/var/log/splunk/scheduler.log 2>/dev/null "
               "| grep -o 'concurrency_limit=[0-9]\\+' | tail -1")
    m = re.search(r"=(\d+)", out)
    return int(m.group(1)) if m else None
