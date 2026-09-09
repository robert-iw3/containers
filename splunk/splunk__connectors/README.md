# Splunk connectors

Connectors that read files, database tables or Parquet, map records through a
schema, and post them to Splunk HEC or to Elasticsearch.

```
core/                shared: config, sources, cursors, schemas, mapping, HEC, Elasticsearch
csv/python/          delimited files
json/python/         JSON Lines
xml/python/          XML, one event per top-level element
sql/python/          polled database tables
parquet/python/      Parquet files, a row group at a time
uat/                 the test rig
*/rust/              Rust ports (see Status)
```

Everything that is not format-specific lives in `core/` in one copy, so a fix
reaches every format rather than one.

## The delivery contract

**A cursor advances only after the destination acknowledges the events it
covers.** Reading is not delivery. A cursor is a byte offset for a file, a
watermark column value for a polled table, and a row-group index for a Parquet
file; the loop treats all three the same way. A crash or a rejected batch causes a
re-read rather than a skip, so the failure mode is a duplicate, which Splunk
can dedupe, rather than a hole, which nothing can recover.

Three outcomes, and what each does to the cursor:

| Outcome | Cause | Cursor |
| --- | --- | --- |
| `DELIVERED` | acknowledged | advances |
| `RETRY` | transport error or 5xx, retries exhausted | holds, re-reads |
| `REJECTED` | 4xx: the payload is wrong and resending cannot help | advances, so one bad batch cannot stall the unit |

## Rules the formats inherit

- **HEC takes newline-delimited JSON objects, never an array.** An array body
  is rejected with code 6 and the whole batch is lost.
- **`time` must be numeric.** ISO 8601 is converted to epoch seconds. A value
  that will not parse omits `time` and carries `time_raw` plus
  `time_parse_failed`, so Splunk applies index time and the unreadable value
  stays visible.
- **An empty value is omitted, not sent as `""`.** Splunk distinguishes the
  two, and `field=""` matches nothing.
- **A record no schema claims is forwarded** under `<format>:unmatched` with
  `schema_match=none`. Dropping it makes an empty dashboard look the same as a
  quiet estate.
- **A failed numeric conversion keeps the event.** The value stays as text and
  is named in `unconverted_numeric_fields`.
- **Schema matching is first-match-wins in file order.** Two schemas claiming
  one key/value is refused at load: the second can never match.

## Configuration

Every setting is read in `core/config.py` and validated at startup, so a bad
value fails with the name of the variable rather than as a traceback at the
first event.

| Variable | Default | Notes |
| --- | --- | --- |
| `<FMT>_LOG_DIR` | `/var/log/<fmt>_data` | directory to tail (file and Parquet sources) |
| `DB_TYPE` | `sqlite` | sqlite, postgres, mysql, mssql, oracle; the driver is imported lazily |
| `DB_CONN_STR` | — | required for the SQL source |
| `SCHEMAS_FILE` | `/app/schemas.yaml` | |
| `STATE_PATH` | `/var/lib/connector/offsets.json` | mount a volume or a restart re-sends |
| `SPLUNK_HEC_URL` | — | required; a placeholder is refused |
| `SPLUNK_TOKEN` | — | required |
| `ES_HOST` / `ES_INDEX` | `http://localhost:9200` | Elasticsearch sink |
| `BATCH_SIZE` | `100` | events per request |
| `WORKER_COUNT` | `2` | concurrent units, not processes |
| `SCAN_INTERVAL` | `5` | seconds between scans (raise it for a polled database) |
| `MAX_RETRIES` | `5` | exponential backoff to `RETRY_CAP_SECONDS` |
| `CSV_DELIMITER` | `,` | configuration, not sniffed |

Discovery is a scan on a timer rather than filesystem notifications: a scan
picks up units already present at startup and does not depend on inotify
working through a bind mount.

A SQL schema names a `table_name` and a watermark (`id_field`, else
`timestamp_field`); only named tables are polled, and a table with neither is
refused at startup because every cycle would otherwise re-send the whole
table. A Parquet schema names a `file_name` and advances a row group at a
time.

## Running the tests

```bash
cd uat && ./run-uat.sh          # every case
KEEP_UP=1 ./run-uat.sh          # leave the rig up
./run-uat.sh csv-trellix        # one case
```

The rig posts to a mock HEC that enforces the real one's rules: token
required, array body rejected, `event` key required, non-numeric `time`
rejected. **`selftest_hec.py` proves the mock first, and a failure there
aborts the run** — a receiver that accepts anything reports a broken connector
as healthy, so its verdicts would be worthless.

Cases cover the shipped schemas, a semicolon delimiter, nested JSON via dotted
paths, XML elements, and the ePO CSV contract proved against a production
export: 50 columns, CRLF, ISO 8601 timestamps, a quoted field holding a comma,
non-ASCII, blank numerics, and a row no schema matches.

Eight cases. `csv-resume` restarts the connector mid-file and asserts that
only appended rows are delivered; `sql-trellix` and `parquet-trellix` restart
and assert that nothing is re-sent. Neither needs a server — SQLite is in the
standard library and Parquet is a file, so there is no reason for those two to
be the untested pair.

`check_delivery.py` reads accepted events back and asserts their content. A
delivered count says events arrived; it does not say the right values arrived
under the right names, which is the failure that survives a green count.

## Status

| Path | State |
| --- | --- |
| `csv`, `json`, `xml`, `sql`, `parquet` `/python` | on `core/`, covered by the suite |
| `*/rust` | not built and not tested here |

**Rust.** `csv/rust` **does not compile** — verified with
`cargo build --release` on `rust:1.90-alpine`, which exits 101:

```
error: unexpected end of macro invocation
   --> src/handler.rs:103:23
    | missing tokens in macro arguments
```

The `json!` at `handler.rs:103` puts a Rust block expression in a value
position, where the macro expects a JSON value. Two more problems are visible
by inspection but unreached, because compilation stops at the first:
`.unwrap_or` given a `String` where `Option<&String>` needs `&String`
(lines 104, 148), and `target.get_mut(k).unwrap_or(&mut json!({}))` borrowing
a temporary (line 137).

Two build-environment defects are fixed: the manifest was named `cargo.toml`
in four of the five crates, which cargo refuses outright ("please try to
rename it to Cargo.toml"), and the Dockerfiles install only `musl-dev` while
`reqwest` pulls `openssl-sys`, which needs `openssl-dev` and `pkgconfig`. The
other four crates are unbuilt; expect the same two classes at least.
