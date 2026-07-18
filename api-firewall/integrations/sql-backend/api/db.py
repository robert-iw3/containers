"""
Shard manager for the record store.

Deterministic sharding: owner_id % len(shards) picks the SQL Server
instance, so routing is stateless and every API replica computes the same
answer (the architecture from this repo's sql/ directory, minus the Redis
lookup — adding a mapping service back is a drop-in change to shard_for()).

Connections are per worker thread per shard (pymssql connections are not
thread-safe), with ping-and-reconnect. All queries are parameterized —
the API layer never interpolates request data into SQL.
"""
import logging
import os
import threading
import time
from typing import List

import pymssql

log = logging.getLogger("uvicorn.error")

DB_NAME = os.environ.get("SQL_DATABASE", "records")
SQL_USER = os.environ.get("SQL_USER", "sa")
SQL_PASSWORD = os.environ["SQL_PASSWORD"]
# "sql1:1433,sql2:1433" -> [("sql1", 1433), ("sql2", 1433)]
SHARDS: List[tuple] = [
    (h.split(":")[0], int(h.split(":")[1]) if ":" in h else 1433)
    for h in os.environ.get("SQL_SHARDS", "sql1:1433").split(",")
    if h.strip()
]

_local = threading.local()

SCHEMA = """
IF OBJECT_ID('dbo.records', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.records (
        id          BIGINT IDENTITY(1,1) PRIMARY KEY,
        owner_id    INT           NOT NULL,
        kind        NVARCHAR(32)  NOT NULL,
        data        NVARCHAR(MAX) NOT NULL,
        created_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
    );
    CREATE INDEX ix_records_owner_kind ON dbo.records (owner_id, kind);
END
"""


def shard_for(owner_id: int) -> int:
    return owner_id % len(SHARDS)


def _connect(shard_id: int, database: str = DB_NAME) -> "pymssql.Connection":
    host, port = SHARDS[shard_id]
    return pymssql.connect(
        server=host,
        port=port,
        user=SQL_USER,
        password=SQL_PASSWORD,
        database=database,
        login_timeout=10,
        timeout=15,
        autocommit=True,
    )


def get_conn(shard_id: int) -> "pymssql.Connection":
    """Thread-local cached connection with ping-and-reconnect."""
    cache = getattr(_local, "conns", None)
    if cache is None:
        cache = _local.conns = {}
    conn = cache.get(shard_id)
    if conn is not None:
        try:
            conn.cursor().execute("SELECT 1")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
    conn = _connect(shard_id)
    cache[shard_id] = conn
    return conn


def bootstrap(max_wait: int = 300) -> None:
    """Create the database and schema on every shard, waiting for each SQL
    Server to come up (cold starts take ~30-60s)."""
    deadline = time.time() + max_wait
    for shard_id, (host, port) in enumerate(SHARDS):
        while True:
            try:
                with _connect(shard_id, database="master") as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "IF DB_ID(%s) IS NULL BEGIN "
                        "DECLARE @sql NVARCHAR(200) = N'CREATE DATABASE ' + QUOTENAME(%s); "
                        "EXEC(@sql) END",
                        (DB_NAME, DB_NAME),
                    )
                with _connect(shard_id) as conn:
                    conn.cursor().execute(SCHEMA)
                log.info("shard %d (%s:%d): schema ready", shard_id, host, port)
                break
            except Exception as exc:
                if time.time() > deadline:
                    raise RuntimeError(
                        f"shard {shard_id} ({host}:{port}) not ready after {max_wait}s: {exc}"
                    ) from exc
                log.info("shard %d (%s:%d) not ready (%s); retrying...",
                         shard_id, host, port, type(exc).__name__)
                time.sleep(3)


def shard_health() -> List[dict]:
    out = []
    for shard_id, (host, port) in enumerate(SHARDS):
        entry = {"shard": shard_id, "server": f"{host}:{port}", "healthy": False, "records": None}
        try:
            cur = get_conn(shard_id).cursor()
            cur.execute("SELECT COUNT(*) FROM dbo.records")
            entry["records"] = cur.fetchone()[0]
            entry["healthy"] = True
        except Exception as exc:
            entry["error"] = type(exc).__name__
        out.append(entry)
    return out
