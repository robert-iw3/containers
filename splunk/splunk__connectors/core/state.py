"""
Durable read offsets, one entry per file.

An offset is meaningless without the identity of the file it points into, so
each entry carries the inode and the size seen at the time. That is what
separates the three cases a restart has to tell apart:

  same inode, file grew        resume at the offset
  same inode, file shrank      truncated in place; restart at 0
  different inode              a new file at a reused path; restart at 0

Offsets are written only after Splunk acknowledges the events they cover, so
a crash re-reads a batch rather than skipping it. Duplicates are recoverable
in Splunk; a hole is not.

The CSV header is stored beside the offset because a resumed read starts mid
file, where there is no header line to find, and a DictReader given the first
data row as its header silently mislabels every field after it.
"""

import json
import os
import tempfile


class OffsetStore:
    def __init__(self, path, log):
        self.path = path
        self.log = log
        self.entries = {}
        self._dirty = False
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return
        except (json.JSONDecodeError, OSError) as exc:
            # Starting over re-sends, which is the recoverable direction.
            self.log.warning("offset file %s unreadable (%s); starting from zero", self.path, exc)
            return
        if isinstance(data, dict):
            self.entries = {k: v for k, v in data.items() if isinstance(v, dict)}
            self.log.info("resumed %d file offsets from %s", len(self.entries), self.path)

    def position(self, path, stat):
        """Byte offset to read from, plus the stored header if it still applies."""
        entry = self.entries.get(path)
        if not entry:
            return 0, None
        if entry.get("inode") != stat.st_ino:
            self.log.info("%s has a new inode; re-reading from the start", path)
            return 0, None
        offset = int(entry.get("offset", 0))
        if stat.st_size < offset:
            self.log.info(
                "%s shrank from %d to %d; re-reading from the start",
                path, offset, stat.st_size,
            )
            return 0, None
        return offset, entry.get("header")

    def commit(self, path, stat, offset, header=None):
        """Record a delivered offset. Called only after a successful send."""
        entry = self.entries.setdefault(path, {})
        entry["inode"] = stat.st_ino
        entry["offset"] = offset
        entry["size"] = stat.st_size
        if header is not None:
            entry["header"] = header
        self._dirty = True

    def forget(self, path):
        if self.entries.pop(path, None) is not None:
            self._dirty = True

    # --- generic cursors, for sources that do not read byte offsets --------
    #
    # A polled table's position is a column value and a Parquet file's is a
    # row-group index, neither of which is a byte offset into a path. They
    # share this store under a namespaced key ("sql:events"), which cannot
    # collide with the absolute paths the file sources use.

    def cursor(self, kind, unit):
        """The stored cursor for one unit, or None."""
        return self.entries.get(f"{kind}:{unit}")

    def set_cursor(self, kind, unit, cursor):
        """Record a delivered cursor. Called only after the sink acknowledges."""
        self.entries[f"{kind}:{unit}"] = dict(cursor)
        self._dirty = True

    def flush(self):
        """Atomic replace: a crash mid-write must not leave a truncated file
        that reads as 'never seen' for every tracked path."""
        if not self._dirty:
            return
        directory = os.path.dirname(self.path) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            handle = tempfile.NamedTemporaryFile(
                "w", dir=directory, prefix=".offsets-", suffix=".tmp",
                delete=False, encoding="utf-8",
            )
            try:
                json.dump(self.entries, handle, indent=1, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                handle.close()
            os.replace(handle.name, self.path)
            self._dirty = False
        except OSError as exc:
            # A connector that cannot persist offsets still delivers; it will
            # re-send after a restart. Losing delivery over bookkeeping is the
            # worse trade, so this is reported and not raised.
            self.log.error("could not write offsets to %s: %s", self.path, exc)
