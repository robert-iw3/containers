import asyncio
from datetime import datetime
from typing import List, Tuple, Optional, Dict
from elasticsearch import AsyncElasticsearch
from prometheus_client import Counter
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()

EVENTS_SENT = Counter("parquet_connector_events_sent_total", "Total events sent to Elastic", ["destination", "schema"])
SEND_ERRORS = Counter("parquet_connector_send_errors_total", "Total send errors to Elastic", ["destination", "schema"])

async def send_to_elastic(
    queue: asyncio.Queue,
    es_host: str,
    es_index: str,
    batch_size: int,
    buffer_timeout: float,
    es_auth: Optional[str] = None,
):
    auth = None
    if es_auth:
        if ":" in es_auth:
            username, password = es_auth.split(":", 1)
            auth = (username, password)
        else:
            auth = {"api_key": es_auth}
    es = AsyncElasticsearch(es_host, basic_auth=auth if isinstance(auth, tuple) else None, api_key=auth.get("api_key") if isinstance(auth, dict) else None)
    batch = []
    last_flush = datetime.now()

    while True:
        try:
            events, file_name, count = await asyncio.wait_for(queue.get(), timeout=buffer_timeout)
            schema_name = file_name.split('.')[0]  # Approximate schema name from file_name
            logger.info(f"Received {count} events from file {file_name}, schema: {schema_name}")
            batch.extend(events)

            if len(batch) >= batch_size or (datetime.now() - last_flush).total_seconds() > buffer_timeout:
                if batch:
                    await _send_batch(es, es_index, batch, schema_name)
                    batch = []
                    last_flush = datetime.now()
        except asyncio.TimeoutError:
            if batch:
                schema_name = file_name.split('.')[0] if 'file_name' in locals() else "unknown"
                await _send_batch(es, es_index, batch, schema_name)
                batch = []
                last_flush = datetime.now()
        except Exception as e:
            schema_name = file_name.split('.')[0] if 'file_name' in locals() else "unknown"
            SEND_ERRORS.labels("elastic", schema_name).inc()
            logger.error(f"Send error: {e}", exc_info=True)
        await asyncio.sleep(0.1)

    await es.close()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=0.1, max=5))
async def _send_batch(es: AsyncElasticsearch, es_index: str, batch: List[Dict], schema_name: str):
    body = []
    for doc in batch:
        body.append({"index": {"_index": es_index}})
        body.append(doc)
    resp = await es.bulk(body=body)
    if resp['errors']:
        SEND_ERRORS.labels("elastic", schema_name).inc()
        logger.error(f"Elastic send failed with errors: {resp['items']}", exc_info=True)
        raise Exception("Bulk index had errors")
    logger.info(f"Sent {len(batch)} events to Elastic, schema: {schema_name}")
    EVENTS_SENT.labels("elastic", schema_name).inc_by(len(batch))