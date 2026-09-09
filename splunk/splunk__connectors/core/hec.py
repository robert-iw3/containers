"""
The HEC client.

HEC reads a request body as a stream of concatenated or newline-separated
JSON OBJECTS. It is not a JSON array endpoint: an array body is rejected with
code 6 and the whole batch is lost, which is what json.dumps(list_of_events)
produces. Framing is therefore this module's main job.

send() reports an outcome rather than raising, because the caller decides
what a failure means for a file offset. Its three results:

  DELIVERED  Splunk acknowledged; the offset may advance.
  RETRY      transport or 5xx, retries exhausted; the offset must not advance
             so the events are read again.
  REJECTED   4xx; the payload is wrong and resending it cannot help. The
             offset advances so one bad batch cannot stall the file forever,
             and the batch is counted and sampled into the log.
"""

import asyncio
import json
import ssl

import aiohttp

DELIVERED = "delivered"
RETRY = "retry"
REJECTED = "rejected"


class Outcome:
    def __init__(self, status, count, detail=""):
        self.status = status
        self.count = count
        self.detail = detail

    @property
    def ok(self):
        return self.status == DELIVERED

    def __repr__(self):
        return f"<Outcome {self.status} n={self.count} {self.detail}>"


def frame(envelopes):
    """Newline-delimited JSON objects, the only shape HEC accepts."""
    return "\n".join(json.dumps(e, separators=(",", ":"), default=str) for e in envelopes)


class HecClient:
    def __init__(self, config, log):
        self.config = config
        self.log = log
        self._session = None
        self._ssl = self._build_ssl()
        self.sent = 0
        self.rejected = 0
        self.retries = 0

    def _build_ssl(self):
        if not self.config.hec_url.lower().startswith("https"):
            return None
        if not self.config.verify_tls:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
        if self.config.ca_file:
            return ssl.create_default_context(cafile=self.config.ca_file)
        return None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        connector = aiohttp.TCPConnector(ssl=self._ssl) if self._ssl is not None else None
        self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self

    async def __aexit__(self, *exc):
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def send(self, envelopes):
        if not envelopes:
            return Outcome(DELIVERED, 0)

        body = frame(envelopes).encode("utf-8")
        headers = {
            "Authorization": f"Splunk {self.config.hec_token}",
            "Content-Type": "application/json",
        }

        delay = self.config.retry_base
        last = ""
        for attempt in range(self.config.max_retries + 1):
            try:
                async with self._session.post(
                    self.config.hec_url, headers=headers, data=body
                ) as response:
                    if response.status == 200:
                        self.sent += len(envelopes)
                        return Outcome(DELIVERED, len(envelopes))

                    text = (await response.text())[:300]
                    last = f"HTTP {response.status}: {text}"

                    # 4xx is a statement about the payload. Resending it
                    # unchanged produces the same answer, so retrying only
                    # stalls the file behind a batch that can never land.
                    if 400 <= response.status < 500 and response.status not in (429,):
                        self.rejected += len(envelopes)
                        sample = json.dumps(envelopes[0], default=str)[:400]
                        self.log.error(
                            "hec rejected %d events, %s; first event: %s",
                            len(envelopes), last, sample,
                        )
                        return Outcome(REJECTED, len(envelopes), last)
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                last = f"{type(exc).__name__}: {exc}"

            if attempt < self.config.max_retries:
                self.retries += 1
                self.log.warning(
                    "hec send failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, self.config.max_retries, delay, last,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.config.retry_cap)

        self.log.error("hec send failed after %d attempts: %s", self.config.max_retries + 1, last)
        return Outcome(RETRY, len(envelopes), last)

    async def health(self):
        """True when the collector answers. Used at startup so a bad token or
        URL is reported once, at the point of configuration, rather than as a
        repeating send failure."""
        base = self.config.hec_url.split("/services/collector")[0]
        url = f"{base}/services/collector/health"
        try:
            async with self._session.get(url) as response:
                return response.status in (200, 400, 401, 403)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return False
