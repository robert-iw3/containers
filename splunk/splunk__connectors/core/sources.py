"""
Sources: where records come from.

A source enumerates units of work and reads one batch from a unit. Everything
after that - schema matching, field mapping, delivery, advancing the cursor -
is identical for every source and lives in runner.py.

The cursor is opaque to the runner: a byte offset for a file, a column value
for a polled table, a row-group index for a Parquet file. The runner's only
rule is the delivery contract - commit a cursor after the sink acknowledges,
never before.
"""

import os

from .schemas import SchemaError


class Batch:
    """Records read from one unit, and the cursor that covers them.

    `more` says another batch is waiting, so the runner loops instead of
    sleeping until the next scan.
    """

    def __init__(self, records, cursor, more=False):
        self.records = records
        self.cursor = cursor
        self.more = more

    def __len__(self):
        return len(self.records)


EMPTY = Batch([], None, False)


class Source:
    """Interface the runner drives. kind namespaces this source's cursors."""

    kind = "source"

    def units(self):
        raise NotImplementedError

    def read(self, unit, cursor):
        raise NotImplementedError

    def schema_for(self, unit, record):
        raise NotImplementedError

    def label(self, unit):
        """What to record as the event's `source` field."""
        return unit

    def close(self):
        pass


class FileSource(Source):
    """Tails files in a directory, reading whole records from a byte offset.

    The header of a delimited file is captured once and stored with the
    cursor: a resumed read starts mid-file where no header line exists, and a
    reader left to find one there treats the first data row as the header.
    """

    kind = "file"

    def __init__(self, config, parser, schemas, log):
        self.config = config
        self.parser = parser
        self.schemas = schemas
        self.log = log

    def units(self):
        try:
            names = sorted(os.listdir(self.config.log_dir))
        except FileNotFoundError:
            self.log.warning("watch directory %s does not exist", self.config.log_dir)
            return []
        return [
            os.path.join(self.config.log_dir, n)
            for n in names
            if n.endswith(self.config.extension)
        ]

    def label(self, unit):
        return os.path.basename(unit)

    def read(self, path, cursor):
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            return EMPTY

        offset, header = self._position(cursor, path, stat)
        if offset >= stat.st_size:
            return EMPTY

        if header is None and offset == 0:
            chunk = self._read_bytes(path, offset, 64 * 1024)
            if not chunk:
                return EMPTY
            header, header_bytes = self.parser.sniff_header(chunk)
            if header is not None:
                offset += header_bytes
            elif self.parser.extension == ".csv":
                return EMPTY

        chunk = self._read_bytes(path, offset, self.config.read_chunk_bytes)
        if not chunk:
            return EMPTY

        records, consumed = self.parser.parse(chunk, header)
        if consumed <= 0:
            # A chunk holding no complete record: only a file still being
            # written does this, so wait for the writer rather than advance.
            return EMPTY

        cursor = {
            "inode": stat.st_ino,
            "offset": offset + consumed,
            "size": stat.st_size,
            "header": header,
        }
        return Batch(records, cursor, more=(offset + consumed) < stat.st_size)

    def _position(self, cursor, path, stat):
        """Where to resume, and the header if it still applies.

        Three cases a restart must tell apart: the file grew (resume), it
        shrank (truncated in place, restart), or the inode changed (a new file
        at a reused path, restart).
        """
        if not cursor:
            return 0, None
        if cursor.get("inode") != stat.st_ino:
            self.log.info("%s has a new inode; re-reading from the start", path)
            return 0, None
        offset = int(cursor.get("offset", 0))
        if stat.st_size < offset:
            self.log.info(
                "%s shrank from %d to %d; re-reading from the start",
                path, offset, stat.st_size,
            )
            return 0, None
        return offset, cursor.get("header")

    def schema_for(self, unit, record):
        return self.schemas.match(record)

    @staticmethod
    def _read_bytes(path, offset, size):
        with open(path, "rb") as handle:
            handle.seek(offset)
            return handle.read(size)


class SqlSource(Source):
    """Polls tables named by the schemas, advancing a watermark column.

    Only tables a schema names are read. Discovering every table in the
    database and forwarding it is not the same thing: it ships whatever
    happens to be there, under no mapping, including tables that are not
    events at all.

    A watermark column is required. Without one a poll can only re-read the
    whole table, and a connector that re-sends its entire history every
    interval is worse than one that refuses to start.
    """

    kind = "sql"

    def __init__(self, config, schemas, log):
        self.config = config
        self.schemas = schemas
        self.log = log
        self._conn = None

        missing = [s.name for s in schemas.schemas if s.table_name and not s.watermark]
        if missing:
            raise SchemaError(
                "these SQL schemas name a table but no id_field or "
                f"timestamp_field: {', '.join(missing)}. A poll needs a column "
                "to advance on, or every cycle re-sends the whole table."
            )

    def units(self):
        return [s.table_name for s in self.schemas.schemas if s.table_name]

    def schema_for(self, unit, record):
        return self.schemas.match_unit(unit)

    def connection(self):
        """Open on first use, then reuse.

        Drivers are imported here rather than at module import: a SQLite
        deployment must not need Oracle's client library installed to start.
        """
        if self._conn is not None:
            return self._conn

        db = self.config.db_type
        conn_str = self.config.db_conn_str
        if db == "sqlite":
            import sqlite3

            self._conn = sqlite3.connect(conn_str)
            self._conn.row_factory = sqlite3.Row
        elif db == "postgres":
            import psycopg2
            import psycopg2.extras

            self._conn = psycopg2.connect(conn_str)
        elif db == "mysql":
            import pymysql

            self._conn = pymysql.connect(**_mysql_params(conn_str))
        elif db == "mssql":
            import pyodbc

            self._conn = pyodbc.connect(conn_str)
        elif db == "oracle":
            import oracledb

            self._conn = oracledb.connect(conn_str)
        else:
            raise SchemaError(f"unsupported DB_TYPE {db!r}")
        return self._conn

    def _quote(self, identifier):
        """Quote an identifier for this dialect.

        Table and column names come from schemas.yaml, not from data, but a
        name that needs quoting (a reserved word, a mixed-case column) fails
        confusingly without it.
        """
        if self.config.db_type == "mysql":
            return "`" + identifier.replace("`", "``") + "`"
        if self.config.db_type == "mssql":
            return "[" + identifier.replace("]", "]]") + "]"
        return '"' + identifier.replace('"', '""') + '"'

    def _placeholder(self):
        return "?" if self.config.db_type in ("sqlite", "mssql") else "%s"

    def _limit_clause(self, sql, limit):
        if self.config.db_type == "mssql":
            return sql.replace("SELECT ", f"SELECT TOP {limit} ", 1)
        if self.config.db_type == "oracle":
            return f"{sql} FETCH FIRST {limit} ROWS ONLY"
        return f"{sql} LIMIT {limit}"

    def read(self, table, cursor):
        schema = self.schemas.match_unit(table)
        if schema is None:
            return EMPTY

        column = schema.watermark
        last = (cursor or {}).get("value")
        quoted_table, quoted_col = self._quote(table), self._quote(column)

        sql = f"SELECT * FROM {quoted_table}"
        params = []
        if last is not None:
            sql += f" WHERE {quoted_col} > {self._placeholder()}"
            params.append(last)
        sql += f" ORDER BY {quoted_col} ASC"
        sql = self._limit_clause(sql, self.config.batch_size)

        conn = self.connection()
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
        finally:
            cur.close()

        if not rows:
            return EMPTY

        records = [dict(zip(columns, tuple(row))) for row in rows]
        highest = records[-1].get(column)
        if highest is None:
            # A NULL watermark cannot advance the cursor, so the next poll
            # would re-read the same rows forever. Stop and say so.
            self.log.error(
                "%s: watermark column %s is NULL on a returned row; "
                "holding the cursor rather than looping on the same rows",
                table, column,
            )
            return EMPTY

        return Batch(
            records,
            {"column": column, "value": _cursor_value(highest)},
            more=len(rows) >= self.config.batch_size,
        )

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None


class ParquetSource(Source):
    """Reads Parquet files a row group at a time.

    Row groups rather than whole files: a Parquet file is often larger than
    the memory a connector should hold, and a group is the unit the format
    already stores separately.
    """

    kind = "parquet"

    def __init__(self, config, schemas, log):
        self.config = config
        self.schemas = schemas
        self.log = log

    def units(self):
        try:
            names = sorted(os.listdir(self.config.log_dir))
        except FileNotFoundError:
            self.log.warning("watch directory %s does not exist", self.config.log_dir)
            return []
        return [
            os.path.join(self.config.log_dir, n)
            for n in names
            if n.endswith(".parquet")
        ]

    def label(self, unit):
        return os.path.basename(unit)

    def schema_for(self, unit, record):
        return self.schemas.match_unit(os.path.basename(unit))

    def read(self, path, cursor):
        import pyarrow.parquet as pq

        try:
            stat = os.stat(path)
        except FileNotFoundError:
            return EMPTY

        handle = pq.ParquetFile(path)
        total = handle.num_row_groups

        group = 0
        if cursor:
            # A rewritten file is a different file. mtime and size together
            # catch a rewrite that keeps the row-group count, which a group
            # index alone would read as "already done".
            same = cursor.get("mtime") == int(stat.st_mtime) and cursor.get("size") == stat.st_size
            if same:
                group = int(cursor.get("group", 0))
            else:
                self.log.info("%s changed on disk; re-reading from the start", path)

        if group >= total:
            return EMPTY

        table = handle.read_row_group(group)
        records = table.to_pylist()

        return Batch(
            records,
            {"group": group + 1, "mtime": int(stat.st_mtime), "size": stat.st_size},
            more=(group + 1) < total,
        )


def _cursor_value(value):
    """Cursors are persisted as JSON, so a datetime or Decimal becomes text.

    The value goes back into a WHERE clause on the next poll, and every
    dialect here compares an ISO 8601 string against a timestamp column
    correctly.
    """
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def _mysql_params(conn_str):
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(conn_str)
    if parsed.scheme not in ("mysql", "mysql+pymysql"):
        raise SchemaError(f"not a MySQL connection string: {conn_str.split('@')[-1]}")
    params = parse_qs(parsed.query)
    return {
        "user": parsed.username,
        "password": parsed.password or "",
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "database": parsed.path.lstrip("/") or params.get("db", [""])[0],
    }
