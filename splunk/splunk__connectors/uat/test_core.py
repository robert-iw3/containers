"""
Unit tests for core/, covering what the integration rig cannot reach.

The rig proves events arrive. These prove the decisions taken on the way:
which timestamps convert, what happens to a field that will not, where an
offset lands when a chunk ends mid-record, and that a batch is never framed
as a JSON array.

    python3 test_core.py
"""

import os
import sys
import tempfile
import unittest

# The connectors root is the parent of uat/ in the repository, and /src when
# the harness container mounts the tree there.
for _root in (os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "/src"):
    if os.path.isdir(os.path.join(_root, "core")):
        sys.path.insert(0, _root)
        break

from core import hec, mapping, timeparse  # noqa: E402
from core.parsers import CsvParser, JsonLinesParser  # noqa: E402
from core.schemas import Schema, SchemaError, Schemas  # noqa: E402
from core.sources import FileSource, SqlSource  # noqa: E402
from core.state import OffsetStore  # noqa: E402


class NullLog:
    def __getattr__(self, _):
        return lambda *a, **k: None


def schema(**cim):
    return Schema({"name": "t", "schema_key": "k", "schema_value": "v",
                   "mappings": {"cim": dict(cim)}}, 0)


class TimeParsing(unittest.TestCase):
    def test_iso_with_milliseconds_and_z(self):
        # The exact shape the ePO exporter writes.
        self.assertEqual(timeparse.to_epoch("2026-09-01T14:20:11.001Z"), 1788272411.001)

    def test_iso_without_subseconds(self):
        self.assertEqual(timeparse.to_epoch("2026-09-01T14:20:11Z"), 1788272411.0)

    def test_iso_with_offset(self):
        self.assertEqual(
            timeparse.to_epoch("2026-09-01T14:20:11+00:00"),
            timeparse.to_epoch("2026-09-01T14:20:11Z"),
        )

    def test_naive_is_treated_as_utc(self):
        self.assertEqual(timeparse.to_epoch("2026-09-01 14:20:11"), 1788272411.0)

    def test_epoch_number_and_string_agree(self):
        self.assertEqual(timeparse.to_epoch(1767225600), 1767225600.0)
        self.assertEqual(timeparse.to_epoch("1767225600"), 1767225600.0)

    def test_epoch_milliseconds_are_scaled(self):
        self.assertEqual(timeparse.to_epoch(1767225600000), 1767225600.0)

    def test_unparseable_is_none_not_a_guess(self):
        for value in ("not a date", "", None, "n/a", "0000-00-00"):
            self.assertIsNone(timeparse.to_epoch(value), value)

    def test_small_number_is_not_a_date(self):
        # A duration or a row counter reaching the time field is a mapping
        # error; 1970 would hide it.
        self.assertIsNone(timeparse.to_epoch(42))
        self.assertIsNone(timeparse.to_epoch("11"))


class Framing(unittest.TestCase):
    def test_batch_is_newline_delimited_not_an_array(self):
        body = hec.frame([{"event": {"a": 1}}, {"event": {"a": 2}}])
        self.assertFalse(body.lstrip().startswith("["))
        self.assertEqual(len(body.splitlines()), 2)

    def test_single_event_has_no_trailing_newline_issue(self):
        self.assertEqual(len(hec.frame([{"event": {"a": 1}}]).splitlines()), 1)

    def test_empty_batch_frames_to_empty(self):
        self.assertEqual(hec.frame([]), "")


class Mapping(unittest.TestCase):
    def test_absent_field_is_omitted_not_empty_string(self):
        # Splunk distinguishes an absent field from "": field="" matches
        # nothing, so writing "" makes a search silently wrong.
        env = mapping.build({"a": ""}, schema(dest="a"), "f.csv", "csv")
        self.assertNotIn("dest", env["event"])

    def test_unconvertible_number_keeps_the_row_and_the_value(self):
        env = mapping.build({"p": "not-a-port"}, schema(dest_port="p"), "f.csv", "csv")
        self.assertEqual(env["event"]["dest_port"], "not-a-port")
        self.assertIn("dest_port", env["event"]["unconverted_numeric_fields"])

    def test_numeric_field_converts(self):
        env = mapping.build({"p": "443"}, schema(dest_port="p"), "f.csv", "csv")
        self.assertEqual(env["event"]["dest_port"], 443)

    def test_iso_time_becomes_epoch(self):
        env = mapping.build(
            {"d": "2026-09-01T14:20:11.001Z"}, schema(time="d"), "f.csv", "csv"
        )
        self.assertEqual(env["time"], 1788272411.001)

    def test_unparseable_time_omits_time_and_keeps_raw(self):
        env = mapping.build({"d": "yesterday"}, schema(time="d"), "f.csv", "csv")
        self.assertNotIn("time", env)
        self.assertEqual(env["event"]["time_raw"], "yesterday")
        self.assertTrue(env["event"]["time_parse_failed"])

    def test_constant_mapping_resolves_to_the_literal(self):
        # protocol: "modbus" in schemas.yaml, where YAML has stripped quotes.
        env = mapping.build({"other": "x"}, schema(protocol="modbus"), "f.csv", "csv")
        self.assertEqual(env["event"]["protocol"], "modbus")

    def test_dotted_path_walks_nested_objects(self):
        env = mapping.build(
            {"destination": {"port": "443"}}, schema(dest_port="destination.port"),
            "f.json", "json",
        )
        self.assertEqual(env["event"]["dest_port"], 443)

    def test_flat_key_wins_over_the_dotted_walk(self):
        env = mapping.build(
            {"a.b": "flat", "a": {"b": "nested"}}, schema(dest="a.b"), "f.json", "json"
        )
        self.assertEqual(env["event"]["dest"], "flat")

    def test_numeric_field_rejects_a_non_numeric_constant(self):
        # A numeric CIM field mapped to a column the record lacks: emitting
        # the column name as the port is worse than having no port.
        env = mapping.build({"other": "x"}, schema(dest_port="dst_port"), "f.csv", "csv")
        self.assertNotIn("dest_port", env["event"])

    def test_constant_resolution_is_reported(self):
        seen = set()
        mapping.build({"other": "x"}, schema(dest="typo_column"), "f.csv", "csv",
                      literals_seen=seen)
        self.assertEqual(seen, {("t", "dest", "typo_column")})

    def test_unmatched_record_is_kept(self):
        env = mapping.build_unmatched({"a": "1", "b": ""}, "f.csv", "csv", "csv:unmatched")
        self.assertEqual(env["sourcetype"], "csv:unmatched")
        self.assertEqual(env["event"]["schema_match"], "none")
        self.assertEqual(env["event"]["a"], "1")


class Schemas_(unittest.TestCase):
    def _write(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_unreachable_duplicate_is_refused(self):
        path = self._write(
            "schemas:\n"
            "  - name: a\n    schema_key: k\n    schema_value: v\n"
            "    mappings: {cim: {time: t}}\n"
            "  - name: b\n    schema_key: k\n    schema_value: v\n"
            "    mappings: {cim: {time: t}}\n"
        )
        with self.assertRaises(SchemaError) as caught:
            Schemas.load(path)
        self.assertIn("unreachable", str(caught.exception))

    def test_first_match_wins_in_file_order(self):
        path = self._write(
            "schemas:\n"
            "  - name: first\n    schema_key: k\n    schema_value: v\n"
            "    mappings: {cim: {time: t}}\n"
            "  - name: second\n    schema_key: k\n    schema_value: w\n"
            "    mappings: {cim: {time: t}}\n"
        )
        loaded = Schemas.load(path)
        self.assertEqual(loaded.match({"k": "v"}).name, "first")
        self.assertIsNone(loaded.match({"k": "nothing"}))

    def test_missing_cim_mapping_is_refused(self):
        path = self._write("schemas:\n  - name: a\n    schema_key: k\n    schema_value: v\n")
        with self.assertRaises(SchemaError):
            Schemas.load(path)


class CsvParsing(unittest.TestCase):
    def setUp(self):
        self.parser = CsvParser()

    def test_crlf_header_is_measured_including_both_bytes(self):
        columns, consumed = self.parser.sniff_header(b"a,b,c\r\n1,2,3\r\n")
        self.assertEqual(columns, ["a", "b", "c"])
        self.assertEqual(consumed, 7)

    def test_lf_header(self):
        columns, consumed = self.parser.sniff_header(b"a,b,c\n1,2,3\n")
        self.assertEqual(columns, ["a", "b", "c"])
        self.assertEqual(consumed, 6)

    def test_header_is_supplied_not_re_read_from_the_chunk(self):
        # This is the resume case: a chunk starting mid file has no header, and
        # a DictReader left to find one eats the first data row.
        records, consumed = self.parser.parse(b"1,2,3\r\n4,5,6\r\n", ["a", "b", "c"])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0], {"a": "1", "b": "2", "c": "3"})
        self.assertEqual(consumed, 14)

    def test_partial_trailing_line_is_not_consumed(self):
        records, consumed = self.parser.parse(b"1,2,3\n4,5", ["a", "b", "c"])
        self.assertEqual(len(records), 1)
        self.assertEqual(consumed, 6)

    def test_quoted_delimiter_and_non_ascii(self):
        records, _ = self.parser.parse(
            'x,"a, b",café\n'.encode("utf-8"), ["one", "two", "three"]
        )
        self.assertEqual(records[0]["two"], "a, b")
        self.assertEqual(records[0]["three"], "café")

    def test_short_row_fills_rather_than_raises(self):
        records, _ = self.parser.parse(b"1,2\n", ["a", "b", "c"])
        self.assertEqual(records[0], {"a": "1", "b": "2", "c": ""})

    def test_long_row_drops_the_unnamed_overflow(self):
        records, _ = self.parser.parse(b"1,2,3,4\n", ["a", "b", "c"])
        self.assertEqual(records[0], {"a": "1", "b": "2", "c": "3"})

    def test_semicolon_delimiter(self):
        parser = CsvParser(delimiter=";")
        columns, _ = parser.sniff_header(b"a;b;c\n")
        self.assertEqual(columns, ["a", "b", "c"])


class JsonParsing(unittest.TestCase):
    def test_whole_lines_only(self):
        records, consumed = JsonLinesParser().parse(b'{"a":1}\n{"a":2', None)
        self.assertEqual(len(records), 1)
        self.assertEqual(consumed, 8)

    def test_malformed_line_is_preserved_not_dropped(self):
        records, _ = JsonLinesParser().parse(b'{"a":1}\nnot json\n', None)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["_parse_error"], "invalid JSON")
        self.assertEqual(records[1]["_raw"], "not json")


class Cursors(unittest.TestCase):
    """The generic cursor store every source shares."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.state = os.path.join(self.dir, "offsets.json")

    def test_cursor_round_trips_through_the_file(self):
        store = OffsetStore(self.state, NullLog())
        store.set_cursor("sql", "epo_events", {"column": "record_id", "value": 42})
        store.flush()
        reloaded = OffsetStore(self.state, NullLog())
        self.assertEqual(
            reloaded.cursor("sql", "epo_events"), {"column": "record_id", "value": 42}
        )

    def test_kinds_do_not_collide(self):
        store = OffsetStore(self.state, NullLog())
        store.set_cursor("sql", "events", {"value": 1})
        store.set_cursor("parquet", "events", {"group": 7})
        self.assertEqual(store.cursor("sql", "events"), {"value": 1})
        self.assertEqual(store.cursor("parquet", "events"), {"group": 7})

    def test_unknown_cursor_is_none(self):
        self.assertIsNone(OffsetStore(self.state, NullLog()).cursor("sql", "nope"))

    def test_unreadable_state_file_starts_over_rather_than_raising(self):
        with open(self.state, "w") as handle:
            handle.write("{ not json")
        store = OffsetStore(self.state, NullLog())
        self.assertIsNone(store.cursor("file", "/x"))


class FileIdentity(unittest.TestCase):
    """Resume, truncation and inode reuse, as FileSource decides them."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.data = os.path.join(self.dir, "f.csv")
        with open(self.data, "w") as handle:
            handle.write("a,b\n1,2\n")
        cfg = type("C", (), {"log_dir": self.dir, "extension": ".csv",
                             "read_chunk_bytes": 65536})()
        self.source = FileSource(cfg, CsvParser(), None, NullLog())

    def test_resume_at_the_stored_offset(self):
        stat = os.stat(self.data)
        cursor = {"inode": stat.st_ino, "offset": 4, "size": stat.st_size,
                  "header": ["a", "b"]}
        self.assertEqual(self.source._position(cursor, self.data, stat), (4, ["a", "b"]))

    def test_truncation_restarts_at_zero(self):
        stat = os.stat(self.data)
        cursor = {"inode": stat.st_ino, "offset": 999, "header": ["a", "b"]}
        self.assertEqual(self.source._position(cursor, self.data, stat), (0, None))

    def test_new_inode_restarts_at_zero(self):
        stat = os.stat(self.data)
        cursor = {"inode": stat.st_ino + 1, "offset": 4, "header": ["a", "b"]}
        self.assertEqual(self.source._position(cursor, self.data, stat), (0, None))

    def test_no_cursor_starts_at_zero(self):
        self.assertEqual(self.source._position(None, self.data, os.stat(self.data)), (0, None))

    def test_units_lists_only_the_matching_extension(self):
        open(os.path.join(self.dir, "other.txt"), "w").close()
        self.assertEqual(self.source.units(), [self.data])


class SqlWatermark(unittest.TestCase):
    """A polled table needs a column to advance on."""

    def _schemas(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return Schemas.load(handle.name)

    def _config(self):
        return type("C", (), {"db_type": "sqlite", "db_conn_str": ":memory:",
                              "batch_size": 100})()

    def test_a_table_without_a_watermark_is_refused_at_startup(self):
        # Without one, every poll re-reads the whole table.
        schemas = self._schemas(
            "schemas:\n  - name: a\n    table_name: t\n"
            "    mappings: {cim: {time: ts}}\n"
        )
        with self.assertRaises(SchemaError) as caught:
            SqlSource(self._config(), schemas, NullLog())
        self.assertIn("re-sends the whole table", str(caught.exception))

    def test_id_field_is_preferred_over_timestamp(self):
        # Two rows sharing a timestamp make a timestamp watermark either skip
        # one or resend both; a monotonic id cannot.
        schemas = self._schemas(
            "schemas:\n  - name: a\n    table_name: t\n"
            "    timestamp_field: ts\n    id_field: rid\n"
            "    mappings: {cim: {time: ts}}\n"
        )
        self.assertEqual(schemas.schemas[0].watermark, "rid")

    def test_units_are_the_named_tables_only(self):
        schemas = self._schemas(
            "schemas:\n  - name: a\n    table_name: t1\n    id_field: rid\n"
            "    mappings: {cim: {time: ts}}\n"
        )
        source = SqlSource(self._config(), schemas, NullLog())
        self.assertEqual(source.units(), ["t1"])

    def test_identifiers_are_quoted_per_dialect(self):
        schemas = self._schemas(
            "schemas:\n  - name: a\n    table_name: t\n    id_field: rid\n"
            "    mappings: {cim: {time: ts}}\n"
        )
        source = SqlSource(self._config(), schemas, NullLog())
        self.assertEqual(source._quote("user"), '"user"')
        source.config.db_type = "mysql"
        self.assertEqual(source._quote("user"), "`user`")
        source.config.db_type = "mssql"
        self.assertEqual(source._quote("user"), "[user]")


if __name__ == "__main__":
    unittest.main(verbosity=2)
