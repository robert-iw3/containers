"""
The connector loop: enumerate units, read a batch, deliver, advance.

The loop knows nothing about where records come from. A source (core/sources.py)
supplies units and batches; everything here is the same whether those units are
files in a directory, tables in a database, or Parquet row groups.

Discovery is a scan on a timer rather than filesystem notifications. A scan
picks up units already present at startup, which a notification watcher never
sees, and does not depend on inotify working through a bind mount. The cost is
up to SCAN_INTERVAL of latency on new data.

One process, one event loop. The work is I/O, so concurrency spans units rather
than processes; blocking reads run in a thread so one slow unit does not stall
the others.
"""

import asyncio
import logging
import os
import signal
import sys
import time

from . import elastic, hec, mapping
from .config import Config, ConfigError
from .schemas import SchemaError, Schemas
from .sources import FileSource
from .state import OffsetStore


def build_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))
        logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    return logger


class Counters:
    def __init__(self):
        self.read = 0
        self.matched = 0
        self.unmatched = 0
        self.delivered = 0
        self.rejected = 0
        self.deferred = 0
        self.units = 0

    def line(self):
        return (
            f"read={self.read} matched={self.matched} unmatched={self.unmatched} "
            f"delivered={self.delivered} rejected={self.rejected} "
            f"deferred={self.deferred} units={self.units}"
        )


class Connector:
    def __init__(self, config, source, log):
        self.config = config
        self.source = source
        self.log = log
        self.schemas = source.schemas
        self.store = source.store
        self.counters = Counters()
        self.unmatched_sourcetype = f"{config.format}:unmatched"
        self._stop = asyncio.Event()
        self._reported_unmatched = set()
        self._reported_literals = set()

    def request_stop(self):
        self._stop.set()

    async def run(self):
        self.log.info("configuration: %s", self.config.redacted())
        self.log.info("schemas: %s", "; ".join(self.schemas.describe()))

        sink_class = (
            hec.HecClient if self.config.sink == "splunk" else elastic.ElasticClient
        )
        destination = (
            self.config.hec_url if self.config.sink == "splunk" else self.config.es_host
        )

        async with sink_class(self.config, self.log) as client:
            self.client = client
            if await client.health():
                self.log.info("destination reachable at %s", destination)
            else:
                # Not fatal: the destination may come up after the connector.
                # Unread input is the visible symptom either way.
                self.log.warning("destination not reachable yet at %s", destination)

            last_status = time.monotonic()
            while not self._stop.is_set():
                try:
                    await self._pass()
                except Exception:
                    self.log.exception("scan failed; continuing")

                self.store.flush()
                now = time.monotonic()
                if now - last_status >= self.config.status_interval:
                    self.log.info("status %s", self.counters.line())
                    last_status = now

                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.config.scan_interval)
                except asyncio.TimeoutError:
                    pass

            self.store.flush()
            self.source.close()
            self.log.info("stopped, final %s", self.counters.line())

    async def _pass(self):
        units = await asyncio.to_thread(self.source.units)
        if not units:
            return

        semaphore = asyncio.Semaphore(self.config.parse_concurrency)

        async def guarded(unit):
            async with semaphore:
                try:
                    await self._drain(unit)
                except Exception:
                    self.log.exception("failed processing %s", unit)

        await asyncio.gather(*(guarded(u) for u in units))

    async def _drain(self, unit):
        """Read and deliver from one unit until it has nothing more ready."""
        while not self._stop.is_set():
            if not await self._batch(unit):
                return

    async def _batch(self, unit):
        cursor = self.store.cursor(self.source.kind, unit)
        batch = await asyncio.to_thread(self.source.read, unit, cursor)
        if not batch or not batch.records:
            return False

        self.counters.read += len(batch.records)
        envelopes = self._envelopes(batch.records, unit)

        deferred = False
        for start in range(0, len(envelopes), self.config.batch_size):
            outcome = await self.client.send(envelopes[start:start + self.config.batch_size])
            if outcome.status == hec.DELIVERED:
                self.counters.delivered += outcome.count
            elif outcome.status == hec.REJECTED:
                # Advancing past a batch the sink will never accept is the
                # only way the rest of the unit is ever read.
                self.counters.rejected += outcome.count
            else:
                self.counters.deferred += outcome.count
                deferred = True
                break

        if deferred:
            self.log.warning(
                "%s: holding the cursor, delivery deferred; this batch will be re-read",
                unit,
            )
            return False

        # The delivery contract: the cursor advances only now, after the sink
        # acknowledged. A crash before this point re-reads rather than skips.
        if batch.cursor is not None:
            self.store.set_cursor(self.source.kind, unit, batch.cursor)
        self.counters.units = len(self.store.entries)
        return batch.more

    def _envelopes(self, records, unit):
        source_label = self.source.label(unit)
        envelopes = []
        unmatched_here = 0
        literals = set()
        for record in records:
            schema = self.source.schema_for(unit, record)
            if schema is None:
                unmatched_here += 1
                self.counters.unmatched += 1
                envelopes.append(
                    mapping.build_unmatched(
                        record, source_label, self.config.format, self.unmatched_sourcetype
                    )
                )
                continue
            self.counters.matched += 1
            extra = {"host": self.config.host} if self.config.host else None
            envelope = mapping.build(
                record, schema, source_label, self.config.format, extra, literals
            )
            if self.config.index and "index" not in envelope:
                envelope["index"] = self.config.index
            envelopes.append(envelope)

        # Once per unit, not once per row: an unmatched schema in a large
        # export otherwise produces one log line per event.
        if unmatched_here and unit not in self._reported_unmatched:
            self._reported_unmatched.add(unit)
            self.log.warning(
                "%s: %d record(s) matched no schema; forwarded as sourcetype %s "
                "so they are searchable rather than dropped",
                source_label, unmatched_here, self.unmatched_sourcetype,
            )

        # A mapping value that is not a field becomes a constant. That is the
        # intended way to write protocol: "modbus", and it is also exactly what
        # a mistyped column name does, so the resolution is reported once.
        new_literals = literals - self._reported_literals
        if new_literals:
            self._reported_literals |= new_literals
            self.log.info(
                "%s: mapped as constants because no such field exists: %s",
                source_label,
                ", ".join(f"{s}.{f}={v!r}" for s, f, v in sorted(new_literals)),
            )
        return envelopes


def main(fmt, log_dir_var, extension, parser_factory=None, sink="splunk",
         source_factory=None):
    """Entry point shared by every connector.

    Pass parser_factory for a file-tailing format, or source_factory for a
    source that is not a file tail.
    """
    log = build_logger(f"{fmt}-{sink}-connector")
    try:
        config = Config(fmt, log_dir_var, extension, sink=sink)
    except ConfigError as exc:
        log.error("configuration error: %s", exc)
        return 2

    try:
        schemas = Schemas.load(config.schemas_file, config.format)
        store = OffsetStore(config.state_path, log)
        if source_factory is not None:
            source = source_factory(config, schemas, log)
        else:
            source = FileSource(config, parser_factory(config), schemas, log)
        # The runner reads both off the source, so every source carries them.
        source.schemas = schemas
        source.store = store
        connector = Connector(config, source, log)
    except (SchemaError, ConfigError) as exc:
        log.error("startup error: %s", exc)
        return 2

    async def run():
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, connector.request_stop)
        await connector.run()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    return 0
