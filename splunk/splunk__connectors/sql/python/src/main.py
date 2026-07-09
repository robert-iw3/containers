import asyncio
import os
import signal
import sys
from dotenv import load_dotenv
import structlog
from structlog.stdlib import LoggerFactory
from prometheus_client import start_http_server
from handler import SqlHandler
from schema import Schemas
from sender import send_to_splunk
from tenacity import retry, stop_after_attempt, wait_exponential

structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=LoggerFactory(),
)

logger = structlog.get_logger()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def start_metrics_server(port: int):
    try:
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}", exc_info=True)
        raise

async def main():
    load_dotenv()
    logger.info("Starting SQL Connector")

    try:
        db_type = os.getenv("DB_TYPE", "postgres")
        conn_str = os.getenv("DB_CONN_STR")
        schemas_file = os.getenv("SCHEMAS_FILE", "/app/schemas.yaml")
        batch_size = int(os.getenv("BATCH_SIZE", "100"))
        buffer_timeout = float(os.getenv("BUFFER_TIMEOUT", "2.0"))
        poll_interval = float(os.getenv("POLL_INTERVAL", "60"))
        state_path = os.getenv("STATE_PATH", "./state.db")
        cdc_enabled = os.getenv("CDC_ENABLED", "false").lower() == "true"
        max_connections_per_table = int(os.getenv("MAX_CONNECTIONS_PER_TABLE", "5"))
        metrics_port = int(os.getenv("METRICS_PORT", "9000"))
        splunk_url = os.getenv("SPLUNK_HEC_URL", "https://your-splunk-host:8088/services/collector/event")
        splunk_token = os.getenv("SPLUNK_TOKEN", "your-splunk-hec-token")
        sqlcipher_key = os.getenv("SQLCIPHER_KEY", None)

        if not conn_str:
            logger.error("DB_CONN_STR not set")
            sys.exit(1)
        if not sqlcipher_key:
            logger.warning("SQLCIPHER_KEY not set, generating random key")
            from secrets import token_hex
            sqlcipher_key = token_hex(16)

        schemas = Schemas.load(schemas_file)
        queue = asyncio.Queue()

        handler = SqlHandler(
            db_type,
            conn_str,
            queue,
            schemas,
            batch_size,
            poll_interval,
            state_path,
            cdc_enabled,
            max_connections_per_table,
            sqlcipher_key,
        )

        # Start metrics server
        await start_metrics_server(metrics_port)

        # Start schema watcher
        schema_task = asyncio.create_task(schemas.watch())

        # Start sender
        sender_task = asyncio.create_task(
            send_to_splunk(queue, splunk_url, splunk_token, batch_size, buffer_timeout)
        )

        # Start handler
        handler_task = asyncio.create_task(handler.start())

        # Handle shutdown
        def handle_shutdown():
            logger.info("Received shutdown signal")
            schema_task.cancel()
            sender_task.cancel()
            handler_task.cancel()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_shutdown)

        await asyncio.gather(schema_task, sender_task, handler_task, return_exceptions=True)
    except Exception as e:
        logger.error(f"Main loop error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())