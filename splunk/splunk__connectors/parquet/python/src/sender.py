import asyncio
from datetime import datetime
from typing import List, Tuple, Dict
import aiohttp
from prometheus_client import Counter
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()

EVENTS_SENT = Counter("parquet_connector_events_sent_total", "Total events sent to Splunk", ["destination"])
SEND_ERRORS = Counter("parquet_connector_send_errors_total", "Total send errors to Splunk", ["destination"])

async def send_to_splunk(
    queue: asyncio.Queue,
    splunk_url: str,
    splunk_token: str,
    batch_size: int,
    buffer_timeout: float,
):
    async with aiohttp.ClientSession() as session:
        batch = []
        last_flush = datetime.now()

        while True:
            try:
                events, file_name, count = await asyncio.wait_for(queue.get(), timeout=buffer_timeout)
                logger.info(f"Received {count} events from file {file_name}")
                batch.extend(events)

                if len(batch) >= batch_size or (datetime.now() - last_flush).total_seconds() > buffer_timeout:
                    if batch:
                        await _send_batch(session, splunk_url, splunk_token, batch)
                        batch = []
                        last_flush = datetime.now()
            except asyncio.TimeoutError:
                if batch:
                    await _send_batch(session, splunk_url, splunk_token, batch)
                    batch = []
                    last_flush = datetime.now()
            except Exception as e:
                SEND_ERRORS.labels("splunk").inc()
                logger.error(f"Send error: {e}", exc_info=True)
            await asyncio.sleep(0.1)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=0.1, max=5))
async def _send_batch(session: aiohttp.ClientSession, splunk_url: str, splunk_token: str, batch: List[Dict]):
    headers = {"Authorization": f"Splunk {splunk_token}", "Content-Type": "application/json"}
    async with session.post(splunk_url, headers=headers, json=batch) as response:
        if response.status != 200:
            SEND_ERRORS.labels("splunk").inc()
            logger.error(f"Splunk send failed: {response.status}", exc_info=True)
            raise Exception(f"HTTP {response.status}")
        logger.info(f"Sent {len(batch)} events to Splunk")
        EVENTS_SENT.labels("splunk").inc_by(len(batch))