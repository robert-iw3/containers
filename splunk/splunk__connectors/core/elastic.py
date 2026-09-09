"""
The Elasticsearch sink.

Plain aiohttp against the _bulk API rather than a client library: the bulk
body is two newline-delimited JSON lines per document and needs no dependency
to build, and elasticsearch_async has been unmaintained since Elasticsearch 6.

The outcome vocabulary matches core.hec so the runner treats both sinks the
same way, including the rule that a file offset advances only on delivery.

_bulk returns HTTP 200 even when individual documents fail, so the per-item
errors flag decides the outcome. Reading only the status code reports a
rejected document as delivered.
"""

import asyncio
import json

import aiohttp

from .hec import DELIVERED, REJECTED, RETRY, Outcome


def to_document(envelope):
    """Flatten a HEC envelope into an Elasticsearch document.

    The envelope's own metadata is kept alongside the event so a document
    carries the same sourcetype and timestamp the Splunk path would use.
    """
    event = dict(envelope.get("event") or {})
    document = {
        "@timestamp": _iso(envelope.get("time")),
        "event": {"dataset": envelope.get("sourcetype", "unknown"), "kind": "event"},
        "source_file": envelope.get("source"),
    }
    document.update(event)
    return document


def _iso(epoch):
    from datetime import datetime, timezone

    if epoch is None:
        return datetime.now(timezone.utc).isoformat()
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def frame(envelopes, index):
    """The _bulk body: an action line and a source line per document."""
    lines = []
    for envelope in envelopes:
        lines.append(json.dumps({"index": {"_index": index}}, separators=(",", ":")))
        lines.append(json.dumps(to_document(envelope), separators=(",", ":"), default=str))
    # _bulk requires the trailing newline.
    return "\n".join(lines) + "\n"


class ElasticClient:
    def __init__(self, config, log):
        self.config = config
        self.log = log
        self._session = None
        self.sent = 0
        self.rejected = 0
        self.retries = 0

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        auth = None
        if self.config.es_user:
            auth = aiohttp.BasicAuth(self.config.es_user, self.config.es_password)
        self._session = aiohttp.ClientSession(timeout=timeout, auth=auth)
        return self

    async def __aexit__(self, *exc):
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def send(self, envelopes):
        if not envelopes:
            return Outcome(DELIVERED, 0)

        url = f"{self.config.es_host.rstrip('/')}/_bulk"
        body = frame(envelopes, self.config.es_index).encode("utf-8")
        headers = {"Content-Type": "application/x-ndjson"}

        delay = self.config.retry_base
        last = ""
        for attempt in range(self.config.max_retries + 1):
            try:
                async with self._session.post(url, headers=headers, data=body) as response:
                    text = await response.text()
                    if response.status == 200:
                        failed = self._failed_items(text)
                        if not failed:
                            self.sent += len(envelopes)
                            return Outcome(DELIVERED, len(envelopes))
                        self.rejected += len(failed)
                        self.log.error(
                            "elasticsearch rejected %d of %d documents; first: %s",
                            len(failed), len(envelopes), json.dumps(failed[0])[:300],
                        )
                        # The rest indexed. Advancing is correct: a document
                        # this cluster refuses will be refused again.
                        self.sent += len(envelopes) - len(failed)
                        return Outcome(REJECTED, len(failed))

                    last = f"HTTP {response.status}: {text[:300]}"
                    if 400 <= response.status < 500 and response.status != 429:
                        self.rejected += len(envelopes)
                        self.log.error("elasticsearch rejected the batch, %s", last)
                        return Outcome(REJECTED, len(envelopes), last)
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                last = f"{type(exc).__name__}: {exc}"

            if attempt < self.config.max_retries:
                self.retries += 1
                self.log.warning(
                    "elasticsearch send failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, self.config.max_retries, delay, last,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.config.retry_cap)

        self.log.error("elasticsearch send failed after %d attempts: %s",
                       self.config.max_retries + 1, last)
        return Outcome(RETRY, len(envelopes), last)

    @staticmethod
    def _failed_items(text):
        try:
            payload = json.loads(text)
        except ValueError:
            return []
        if not payload.get("errors"):
            return []
        failed = []
        for item in payload.get("items", []):
            result = next(iter(item.values()), {})
            if result.get("error"):
                failed.append(result["error"])
        return failed

    async def health(self):
        url = f"{self.config.es_host.rstrip('/')}/"
        try:
            async with self._session.get(url) as response:
                return response.status < 500
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return False
