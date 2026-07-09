import asyncio
import json
import sqlite3
from collections import defaultdict
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import pyarrow
import pyarrow.parquet as pq
import pyarrow.dataset as ds
from prometheus_client import Counter, Gauge, Histogram
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
from schema import Schema, Schemas
from secrets import token_hex
import aiofiles
import watchfiles
import os
import psutil

logger = structlog.get_logger()

EVENTS_PROCESSED = Counter("parquet_connector_events_processed_total", "Total events processed per file", ["file", "schema"])
ERRORS_TOTAL = Counter("parquet_connector_errors_total", "Total errors per file", ["file", "schema"])
PROCESSING_LATENCY = Histogram("parquet_connector_processing_latency_seconds", "Processing latency per file", ["file", "schema"])
ACTIVE_FILES = Gauge("parquet_connector_active_files", "Active Parquet files being processed", ["schema"])

class HandlerError(Exception):
    pass

class Position:
    def __init__(self, kind: str, value: Union[datetime, str, int]):
        self.kind = kind
        self.value = value

    def to_dict(self) -> Dict:
        return {"kind": self.kind, "value": str(self.value) if isinstance(self.value, datetime) else self.value}

    @classmethod
    def from_dict(cls, data: Dict) -> "Position":
        kind = data["kind"]
        value = data["value"]
        if kind == "Timestamp":
            value = datetime.fromisoformat(value)
        elif kind == "Offset":
            value = int(value)
        return cls(kind, value)

class ParquetHandler:
    def __init__(
        self,
        data_dir: str,
        sender_queue: asyncio.Queue,
        schemas: Schemas,
        batch_size: int,
        poll_interval: float,
        state_path: str,
        incremental_enabled: bool,
        max_files_concurrent: int,
        max_memory_mb: int,
        sqlcipher_key: str = token_hex(16),
    ):
        if not (1 <= batch_size <= 1000):
            raise HandlerError("batch_size must be between 1 and 1000")
        if not (1 <= poll_interval <= 3600):
            raise HandlerError("poll_interval must be between 1 and 3600 seconds")
        if not (1 <= max_files_concurrent <= 50):
            raise HandlerError("max_files_concurrent must be between 1 and 50")
        if not (100 <= max_memory_mb <= 8192):
            raise HandlerError("max_memory_mb must be between 100 and 8192 MB")

        self.data_dir = Path(data_dir).resolve()
        if not self.data_dir.is_dir():
            raise HandlerError(f"Data directory {data_dir} does not exist")
        if not os.access(self.data_dir, os.R_OK):
            raise HandlerError(f"No read permission for {data_dir}")

        self.sender_queue = sender_queue
        self.schemas = schemas
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.state_path = state_path
        self.incremental_enabled = incremental_enabled
        self.max_files_concurrent = max_files_concurrent
        self.max_memory_mb = max_memory_mb
        self.sqlcipher_key = sqlcipher_key
        self.active_files: set = set()
        self.last_positions: Dict[str, Position] = self._load_state()

    def _load_state(self) -> Dict[str, Position]:
        try:
            with sqlite3.connect(f"file:{self.state_path}?mode=rw", uri=True) as conn:
                conn.execute(f"PRAGMA key='{self.sqlcipher_key}'")
                conn.execute("CREATE TABLE IF NOT EXISTS positions (file_name TEXT PRIMARY KEY, position TEXT)")
                cursor = conn.cursor()
                cursor.execute("SELECT file_name, position FROM positions")
                return {row[0]: Position.from_dict(json.loads(row[1])) for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error(f"State load error: {e}", exc_info=True)
            return {}

    def _save_state(self, file_name: str, position: Position):
        try:
            with sqlite3.connect(f"file:{self.state_path}?mode=rw", uri=True) as conn:
                conn.execute(f"PRAGMA key='{self.sqlcipher_key}'")
                conn.execute("INSERT OR REPLACE INTO positions (file_name, position) VALUES (?, ?)",
                             (file_name, json.dumps(position.to_dict())))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"State save error: {e}", exc_info=True)

    async def start(self):
        if self.incremental_enabled:
            await self._start_incremental()
        else:
            await self._start_full_scan()

    async def _discover_files(self) -> List[Path]:
        logger.info("Discovering Parquet files")
        try:
            start = datetime.now()
            files = [f for f in self.data_dir.glob("*.parquet") if os.access(f, os.R_OK)]
            PROCESSING_LATENCY.labels("discover", "global").observe((datetime.now() - start).total_seconds())
            logger.debug(f"Discovered {len(files)} Parquet files")
            return files
        except Exception as e:
            logger.error(f"File discovery error: {e}", exc_info=True)
            raise HandlerError(f"Failed to discover files: {e}")

    async def _start_full_scan(self):
        while True:
            try:
                files = await self._discover_files()
                for file in files:
                    if len(self.active_files) >= self.max_files_concurrent:
                        await asyncio.sleep(0.1)
                        continue
                    try:
                        await self._process_file(file)
                    except Exception as e:
                        schema_name = self.schemas.get_schema(file.name).name if self.schemas.get_schema(file.name) else "unknown"
                        ERRORS_TOTAL.labels(file.name, schema_name).inc()
                        logger.error(f"Error processing file {file}: {e}", exc_info=True)
            except Exception as e:
                ERRORS_TOTAL.labels("discover", "global").inc()
                logger.error(f"Error discovering files: {e}", exc_info=True)
            await asyncio.sleep(self.poll_interval)

    async def _start_incremental(self):
        async for changes in watchfiles.awatch(self.data_dir, watch_filter=watchfiles.filters.RegexFilter(r".*\.parquet$")):
            try:
                files = await self._discover_files()
                for file in files:
                    if len(self.active_files) >= self.max_files_concurrent:
                        await asyncio.sleep(0.1)
                        continue
                    try:
                        await self._process_file(file)
                    except Exception as e:
                        schema_name = self.schemas.get_schema(file.name).name if self.schemas.get_schema(file.name) else "unknown"
                        ERRORS_TOTAL.labels(file.name, schema_name).inc()
                        logger.error(f"Error processing file {file}: {e}", exc_info=True)
            except Exception as e:
                ERRORS_TOTAL.labels("discover", "global").inc()
                logger.error(f"Error discovering files: {e}", exc_info=True)

    async def _process_file(self, file: Path):
        file_name = file.name
        if file_name in self.active_files:
            return
        self.active_files.add(file_name)
        schema = self.schemas.get_schema(file_name)
        schema_name = schema.name if schema else "unknown"
        ACTIVE_FILES.labels(schema_name).inc()

        if not schema:
            logger.warning(f"No schema found for file {file_name}")
            self.active_files.remove(file_name)
            ACTIVE_FILES.labels(schema_name).dec()
            return

        logger.info(f"Processing file: {file_name}, schema: {schema_name}")
        async with AsyncExitStack() as stack:
            try:
                start = datetime.now()
                # Check memory constraints
                mem_available = psutil.virtual_memory().available // (1024 ** 2)  # MB
                if mem_available < self.max_memory_mb:
                    raise HandlerError(f"Insufficient memory: {mem_available}MB available, {self.max_memory_mb}MB required")

                # Try as single Parquet file, then as dataset
                try:
                    parquet_file = pq.ParquetFile(file)
                    schema_arrow = parquet_file.schema_arrow
                    is_dataset = False
                except pyarrow.ArrowInvalid:
                    dataset = ds.dataset(file, format="parquet")
                    schema_arrow = dataset.schema
                    is_dataset = True

                missing_fields = self._validate_schema(schema_arrow, schema)
                if missing_fields:
                    raise HandlerError(f"Schema mismatch for file {file_name}: missing fields {missing_fields}")

                pos = self.last_positions.get(file_name)
                start_row = 0 if not pos or pos.kind != "Offset" else pos.value
                new_pos = pos

                batch = []
                if is_dataset:
                    # Process partitioned dataset
                    for fragment in dataset.get_fragments():
                        for batch_record in fragment.to_table().to_batches():
                            df = batch_record.to_pandas()
                            for _, row in df.iterrows():
                                if start_row > 0:
                                    start_row -= 1
                                    continue
                                event = row.to_dict()
                                if self.incremental_enabled and schema.timestamp_field:
                                    ts = event.get(schema.timestamp_field)
                                    if ts and pos and pos.kind == "Timestamp" and ts <= pos.value:
                                        continue
                                transformed = self._transform_to_ecs(event, schema)
                                batch.append(transformed)
                                EVENTS_PROCESSED.labels(file_name, schema_name).inc()

                                if schema.timestamp_field and (ts := event.get(schema.timestamp_field)):
                                    new_pos = Position("Timestamp", ts)
                                else:
                                    new_pos = Position("Offset", start_row + len(df))

                                if len(batch) >= self.batch_size:
                                    await self.sender_queue.put((batch, file_name, len(batch)))
                                    batch = []
                else:
                    # Process single Parquet file
                    num_rows = parquet_file.metadata.num_rows
                    for batch_idx in range(parquet_file.num_row_groups):
                        if start_row >= num_rows:
                            break
                        table = parquet_file.read_row_group(batch_idx, use_memory_map=True)
                        df = table.to_pandas()
                        for _, row in df.iterrows():
                            if start_row > 0:
                                start_row -= 1
                                continue
                            event = row.to_dict()
                            if self.incremental_enabled and schema.timestamp_field:
                                ts = event.get(schema.timestamp_field)
                                if ts and pos and pos.kind == "Timestamp" and ts <= pos.value:
                                    continue
                            transformed = self._transform_to_ecs(event, schema)
                            batch.append(transformed)
                            EVENTS_PROCESSED.labels(file_name, schema_name).inc()

                            if schema.timestamp_field and (ts := event.get(schema.timestamp_field)):
                                new_pos = Position("Timestamp", ts)
                            else:
                                new_pos = Position("Offset", start_row + len(df))

                            if len(batch) >= self.batch_size:
                                await self.sender_queue.put((batch, file_name, len(batch)))
                                batch = []

                if batch:
                    await self.sender_queue.put((batch, file_name, len(batch)))

                if new_pos:
                    self.last_positions[file_name] = new_pos
                    self._save_state(file_name, new_pos)

                PROCESSING_LATENCY.labels(file_name, schema_name).observe((datetime.now() - start).total_seconds())
            except pyarrow.ArrowInvalid as e:
                ERRORS_TOTAL.labels(file_name, schema_name).inc()
                logger.error(f"Invalid Parquet file {file_name}: {e}", exc_info=True)
                raise HandlerError(f"Failed to process file {file_name}: {e}")
            except OSError as e:
                ERRORS_TOTAL.labels(file_name, schema_name).inc()
                logger.error(f"File access error for {file_name}: {e}", exc_info=True)
                raise HandlerError(f"Failed to process file {file_name}: {e}")
            except Exception as e:
                ERRORS_TOTAL.labels(file_name, schema_name).inc()
                logger.error(f"File processing error for {file_name}: {e}", exc_info=True)
                raise HandlerError(f"Failed to process file {file_name}: {e}")
            finally:
                self.active_files.remove(file_name)
                ACTIVE_FILES.labels(schema_name).dec()

    def _validate_schema(self, arrow_schema, schema: Schema) -> List[str]:
        expected_fields = set(v for k, v in schema.mappings.ecs.items() if k != "sourcetype" and not v.startswith('"'))
        actual_fields = set(arrow_schema.names)
        missing_fields = expected_fields - actual_fields
        if missing_fields:
            logger.warning(f"Schema validation failed: missing fields {missing_fields} in {schema.file_name}")
        return list(missing_fields)

    def _transform_to_ecs(self, event: Dict, schema: Schema) -> Dict:
        ecs = {
            "@timestamp": event.get(schema.mappings.ecs.get("@timestamp", "timestamp"), datetime.utcnow().isoformat()),
            "ecs": {"version": "8.0.0"},
        }
        for key, value in schema.mappings.ecs.items():
            if not key.startswith("@"):
                if value.startswith('"') and value.endswith('"'):
                    ecs[key] = value.strip('"')
                else:
                    ecs[key] = event.get(value, "")
        return ecs