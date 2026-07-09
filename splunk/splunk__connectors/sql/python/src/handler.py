import asyncio
import json
import sqlite3
from collections import defaultdict
from contextlib import AsyncExitStack
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse, parse_qs
import oracledb
import psycopg2
from psycopg2.extras import LogicalReplicationConnection
import pyodbc
import pymysql
from prometheus_client import Counter, Gauge, Histogram
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
from schema import Schema, Schemas
from secrets import token_hex

logger = structlog.get_logger()

EVENTS_PROCESSED = Counter("sql_connector_events_processed_total", "Total events processed per table", ["table"])
ERRORS_TOTAL = Counter("sql_connector_errors_total", "Total errors per table", ["table"])
QUERY_LATENCY = Histogram("sql_connector_query_latency_seconds", "Query latency per table", ["table"])
ACTIVE_CONNECTIONS = Gauge("sql_connector_active_connections", "Active database connections")

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
        elif kind == "Id":
            value = value  # UUID as string
        elif kind == "Lsn":
            value = int(value)
        return cls(kind, value)

class SqlHandler:
    def __init__(
        self,
        db_type: str,
        conn_str: str,
        sender_queue: asyncio.Queue,
        schemas: Schemas,
        batch_size: int,
        poll_interval: float,
        state_path: str,
        cdc_enabled: bool,
        max_connections_per_table: int,
        sqlcipher_key: str = token_hex(16),
    ):
        if not (1 <= batch_size <= 1000):
            raise HandlerError("batch_size must be between 1 and 1000")
        if not (1 <= poll_interval <= 3600):
            raise HandlerError("poll_interval must be between 1 and 3600 seconds")
        if not (1 <= max_connections_per_table <= 50):
            raise HandlerError("max_connections_per_table must be between 1 and 50")

        self.db_type = db_type.lower()
        self.conn_str = conn_str
        self.sender_queue = sender_queue
        self.schemas = schemas
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.state_path = state_path
        self.cdc_enabled = cdc_enabled
        self.max_connections_per_table = max_connections_per_table
        self.sqlcipher_key = sqlcipher_key
        self.pools: Dict[str, List] = defaultdict(list)
        self.last_positions: Dict[str, Position] = self._load_state()
        self._validate_db_type()

    def _validate_db_type(self):
        valid_types = {"postgres", "mysql", "mssql", "sqlite", "oracle"}
        if self.db_type not in valid_types:
            raise HandlerError(f"Unsupported database type: {self.db_type}")

    def _load_state(self) -> Dict[str, Position]:
        try:
            with sqlite3.connect(f"file:{self.state_path}?mode=rw", uri=True) as conn:
                conn.execute(f"PRAGMA key='{self.sqlcipher_key}'")
                conn.execute("CREATE TABLE IF NOT EXISTS positions (table_name TEXT PRIMARY KEY, position TEXT)")
                cursor = conn.cursor()
                cursor.execute("SELECT table_name, position FROM positions")
                return {row[0]: Position.from_dict(json.loads(row[1])) for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error(f"State load error: {e}", exc_info=True)
            return {}

    def _save_state(self, table: str, position: Position):
        try:
            with sqlite3.connect(f"file:{self.state_path}?mode=rw", uri=True) as conn:
                conn.execute(f"PRAGMA key='{self.sqlcipher_key}'")
                conn.execute("INSERT OR REPLACE INTO positions (table_name, position) VALUES (?, ?)",
                             (table, json.dumps(position.to_dict())))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"State save error: {e}", exc_info=True)

    async def start(self):
        if self.cdc_enabled and self.db_type == "postgres":
            await self._start_cdc()
        else:
            await self._start_polling()

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=0.1, max=10))
    async def _get_connection(self, table: Optional[str] = None):
        async with AsyncExitStack() as stack:
            if table and table in self.pools and len(self.pools[table]) < self.max_connections_per_table:
                ACTIVE_CONNECTIONS.set(sum(len(pool) for pool in self.pools.values()))
                return self.pools[table][-1]

            if self.db_type == "postgres":
                conn = stack.enter_context(psycopg2.connect(self.conn_str))
            elif self.db_type == "mysql":
                conn = stack.enter_context(pymysql.connect(**self._parse_mysql_conn_str()))
            elif self.db_type == "mssql":
                conn = stack.enter_context(pyodbc.connect(self.conn_str))
            elif self.db_type == "sqlite":
                conn = stack.enter_context(sqlite3.connect(self.conn_str))
            elif self.db_type == "oracle":
                conn = stack.enter_context(oracledb.connect(self.conn_str))
            else:
                raise HandlerError("Unknown database type")

            if table:
                if len(self.pools[table]) >= self.max_connections_per_table:
                    self.pools[table].pop(0).close()
                self.pools[table].append(conn)
            ACTIVE_CONNECTIONS.set(sum(len(pool) for pool in self.pools.values()))
            return conn

    def _parse_mysql_conn_str(self) -> Dict:
        parsed = urlparse(self.conn_str)
        if parsed.scheme != "mysql":
            raise HandlerError("Invalid MySQL connection string")
        params = parse_qs(parsed.query)
        return {
            "user": parsed.username,
            "password": parsed.password,
            "host": parsed.hostname,
            "port": parsed.port or 3306,
            "database": parsed.path.lstrip("/") or params.get("db", [""])[0],
        }

    async def _discover_tables(self) -> List[str]:
        logger.info("Discovering tables")
        async with AsyncExitStack() as stack:
            conn = await self._get_connection(None)
            stack.push(conn)
            try:
                start = datetime.now()
                cursor = conn.cursor()
                if self.db_type == "postgres":
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND (table_type = 'BASE TABLE' OR table_type = 'VIEW')")
                elif self.db_type == "mysql":
                    cursor.execute("SHOW TABLES")
                elif self.db_type == "mssql":
                    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' OR TABLE_TYPE = 'VIEW'")
                elif self.db_type == "sqlite":
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' OR type='view'")
                elif self.db_type == "oracle":
                    cursor.execute("SELECT TABLE_NAME FROM USER_TABLES UNION SELECT VIEW_NAME AS TABLE_NAME FROM USER_VIEWS")

                tables = [row[0] for row in cursor.fetchall()]
                QUERY_LATENCY.labels("discover").observe((datetime.now() - start).total_seconds())
                logger.debug(f"Discovered tables: {tables}")
                return tables
            except Exception as e:
                logger.error(f"Table discovery error: {e}", exc_info=True)
                raise HandlerError(f"Failed to discover tables: {e}")

    async def _start_polling(self):
        while True:
            try:
                tables = await self._discover_tables()
                for table in tables:
                    try:
                        await self._process_table(table)
                    except Exception as e:
                        ERRORS_TOTAL.labels(table).inc()
                        logger.error(f"Error processing table {table}: {e}", exc_info=True)
            except Exception as e:
                ERRORS_TOTAL.labels("discover").inc()
                logger.error(f"Error discovering tables: {e}", exc_info=True)
            await asyncio.sleep(self.poll_interval)

    async def _start_cdc(self):
        if self.db_type != "postgres":
            raise HandlerError("CDC only supported for PostgreSQL")

        async with AsyncExitStack() as stack:
            conn = stack.enter_context(psycopg2.connect(self.conn_str, connection_factory=LogicalReplicationConnection))
            cursor = stack.enter_context(conn.cursor())
            try:
                cursor.execute("CREATE PUBLICATION sql_connector_pub FOR ALL TABLES")
                cursor.execute("CREATE_REPLICATION_SLOT sql_connector_slot LOGICAL pgoutput")
                cursor.start_replication(slot_name="sql_connector_slot", decode=True)

                cdc_queue = asyncio.Queue(maxsize=self.batch_size)

                async def process_messages():
                    while True:
                        batch = []
                        start = datetime.now()
                        for _ in range(self.batch_size):
                            try:
                                msg = await asyncio.wait_for(cdc_queue.get(), timeout=1.0)
                                if msg.data_type == "INSERT":
                                    table = msg.relation_name
                                    if schema := self.schemas.get_schema(table):
                                        event = {col: val for col, val in zip(msg.column_names, msg.column_values)}
                                        transformed = self._transform_to_cim(event, schema)
                                        batch.append(transformed)
                                        EVENTS_PROCESSED.labels(table).inc()
                                        if lsn := msg.lsn:
                                            self.last_positions[table] = Position("Lsn", lsn)
                                            self._save_state(table, self.last_positions[table])
                                msg.ack()
                            except asyncio.TimeoutError:
                                break
                        if batch:
                            await self.sender_queue.put((batch, table, len(batch)))
                        QUERY_LATENCY.labels("cdc").observe((datetime.now() - start).total_seconds())

                def consume_stream():
                    def process_msg(msg):
                        asyncio.create_task(cdc_queue.put(msg))
                    cursor.consume_stream(process_msg)

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, consume_stream)
            except Exception as e:
                logger.error(f"CDC error: {e}", exc_info=True)
                raise HandlerError(f"CDC failed: {e}")

    async def _process_table(self, table: str):
        schema = self.schemas.get_schema(table)
        if not schema:
            logger.warning(f"No schema found for table {table}")
            return

        logger.info(f"Processing table: {table}")
        async with AsyncExitStack() as stack:
            conn = await self._get_connection(table)
            stack.push(conn)
            try:
                start = datetime.now()
                query = f'SELECT * FROM "{table}" WHERE 1=1'
                pos = self.last_positions.get(table)
                order_field = "1"
                filter_clause = ""

                if schema.timestamp_field and pos and pos.kind == "Timestamp":
                    order_field = schema.timestamp_field
                    filter_clause = f' AND "{schema.timestamp_field}" > \'{pos.value}\''
                elif schema.id_field and pos and pos.kind == "Id":
                    order_field = schema.id_field
                    filter_clause = f' AND "{schema.id_field}" > \'{pos.value}\''
                elif schema.timestamp_field:
                    order_field = schema.timestamp_field
                elif schema.id_field:
                    order_field = schema.id_field
                else:
                    logger.warning(f"No incremental field for table {table}, full scan")

                query += filter_clause + f' ORDER BY "{order_field}" ASC LIMIT {self.batch_size}'
                logger.debug(f"Executing query: {query}")

                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                QUERY_LATENCY.labels(table).observe((datetime.now() - start).total_seconds())

                batch = []
                new_pos = pos
                for row in rows:
                    event = dict(zip(columns, row))
                    transformed = self._transform_to_cim(event, schema)
                    batch.append(transformed)

                    if schema.timestamp_field and (ts := event.get(schema.timestamp_field)):
                        new_pos = Position("Timestamp", ts)
                    elif schema.id_field and (id_ := event.get(schema.id_field)):
                        new_pos = Position("Id", id_)

                    EVENTS_PROCESSED.labels(table).inc()

                if new_pos:
                    self.last_positions[table] = new_pos
                    self._save_state(table, new_pos)

                if batch:
                    logger.info(f"Sending batch of {len(batch)} events for table {table}")
                    await self.sender_queue.put((batch, table, len(batch)))
            except Exception as e:
                ERRORS_TOTAL.labels(table).inc()
                logger.error(f"Table processing error: {e}", exc_info=True)
                raise HandlerError(f"Failed to process table {table}: {e}")

    def _transform_to_cim(self, event: Dict, schema: Schema) -> Dict:
        cim = {
            "time": event.get(schema.mappings.cim.get("time", "timestamp"), datetime.utcnow().timestamp()),
            "vendor_product": "SQL_Connector",
            "schema": schema.name,
        }

        for key, value in schema.mappings.cim.items():
            if key != "sourcetype":
                if value.startswith('"') and value.endswith('"'):
                    cim[key] = value.strip('"')
                else:
                    cim[key] = event.get(value, "")

        return {
            "event": cim,
            "sourcetype": schema.mappings.cim.get("sourcetype", f"sql:{schema.name}")
        }