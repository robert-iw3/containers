"""
Schema loading and record matching.

Matching is first-match-wins in file order, so order is load-bearing and the
loader says so rather than leaving it to be discovered. A record that matches
nothing is an explicit outcome - UNMATCHED - and never a silent drop: an
event the connector could not classify is still an event that happened, and
dropping it makes an empty dashboard indistinguishable from a quiet estate.
"""

import yaml


class SchemaError(Exception):
    pass


UNMATCHED = "__unmatched__"


class Schema:
    def __init__(self, raw, ordinal):
        try:
            self.name = raw["name"]
        except (KeyError, TypeError):
            raise SchemaError(f"schema #{ordinal} has no name")

        self.ordinal = ordinal
        self.raw = raw
        # Three ways a schema claims a record, one per source kind.
        # File sources discriminate on a field's value; a SQL source on the
        # table the row came from; a Parquet source on the file name.
        self.key = raw.get("schema_key")
        self.value = raw.get("schema_value")
        self.root_element = raw.get("root_element")
        self.namespace = raw.get("namespace", "")
        self.table_name = raw.get("table_name")
        self.file_name = raw.get("file_name")

        # The watermark column for a polled source: the connector asks for
        # rows greater than the last value it delivered. Without one, a table
        # can only be read whole, so the loader refuses that below.
        self.timestamp_field = raw.get("timestamp_field")
        self.id_field = raw.get("id_field")

        mappings = raw.get("mappings") or {}
        self.cim = dict(mappings.get("cim") or {})
        if not self.cim:
            raise SchemaError(f"schema {self.name!r} has no mappings.cim")

        # sourcetype is metadata about the event, not a field on it.
        self.sourcetype = self.cim.pop("sourcetype", None) or f"csv:{self.name}"
        self.time_field = self.cim.get("time")
        self.index = raw.get("index")

    def matches(self, record):
        if self.key is None:
            return False
        return str(record.get(self.key, "")) == str(self.value)

    def matches_element(self, root_element, namespace):
        if self.root_element is None:
            return False
        return self.root_element == root_element and self.namespace == (namespace or "")

    def matches_unit(self, unit):
        """True when this schema claims a named table or file."""
        return unit in (self.table_name, self.file_name) and unit is not None

    @property
    def watermark(self):
        """The column a polled source orders and filters by, or None.

        id_field is preferred over timestamp_field: a monotonic id cannot go
        backwards, while two rows sharing a timestamp make a timestamp
        watermark either skip one or resend both.
        """
        return self.id_field or self.timestamp_field


class Schemas:
    def __init__(self, schemas, path):
        self.schemas = schemas
        self.path = path

    @classmethod
    def load(cls, path, default_sourcetype_prefix="csv"):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except FileNotFoundError:
            raise SchemaError(f"schemas file not found: {path}")
        except yaml.YAMLError as exc:
            raise SchemaError(f"{path} is not valid YAML: {exc}")

        if not isinstance(data, dict) or "schemas" not in data:
            raise SchemaError(f"{path} has no top-level 'schemas' key")
        entries = data["schemas"]
        if not isinstance(entries, list) or not entries:
            raise SchemaError(f"{path} defines no schemas")

        schemas = []
        for ordinal, raw in enumerate(entries):
            schema = Schema(raw, ordinal)
            if schema.sourcetype.startswith("csv:") and default_sourcetype_prefix != "csv":
                schema.sourcetype = f"{default_sourcetype_prefix}:{schema.name}"
            schemas.append(schema)

        # Two schemas testing the same key for the same value: the second can
        # never match, so report it rather than let it look configured.
        seen = {}
        for schema in schemas:
            if schema.key is None:
                continue
            token = (schema.key, str(schema.value))
            if token in seen:
                raise SchemaError(
                    f"schema {schema.name!r} duplicates the match "
                    f"{schema.key}={schema.value!r} already claimed by {seen[token]!r}; "
                    "first match wins, so this one is unreachable"
                )
            seen[token] = schema.name

        return cls(schemas, path)

    def match(self, record):
        """First schema whose key equals its value, or None."""
        for schema in self.schemas:
            if schema.matches(record):
                return schema
        return None

    def match_element(self, root_element, namespace):
        for schema in self.schemas:
            if schema.matches_element(root_element, namespace):
                return schema
        return None

    def match_unit(self, unit):
        """First schema claiming a named table or file, or None."""
        for schema in self.schemas:
            if schema.matches_unit(unit):
                return schema
        return None

    def units(self):
        """Every table or file name any schema names."""
        return [s.table_name or s.file_name for s in self.schemas
                if s.table_name or s.file_name]

    def describe(self):
        """One line per schema, naming how it is selected."""
        out = []
        for s in self.schemas:
            if s.key:
                how = f"{s.key}={s.value!r}"
            elif s.root_element:
                how = f"<{s.root_element}>"
            elif s.table_name:
                how = f"table {s.table_name} on {s.watermark}"
            elif s.file_name:
                how = f"file {s.file_name}"
            else:
                how = "UNSELECTABLE"
            out.append(f"{s.ordinal}:{s.name} ({how} -> {s.sourcetype})")
        return out
