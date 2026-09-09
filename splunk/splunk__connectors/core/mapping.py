"""
Build the HEC envelope for one parsed record.

Three rules, each replacing a defect:

  A field the schema maps to a missing or empty column is omitted. Splunk
  treats an absent field and an empty string differently - `field=""` matches
  nothing - so writing "" for absent data makes a search silently wrong.

  A numeric conversion that fails does not discard the record. The value is
  carried through as text and the event still ships; losing an event because
  one port was blank is a worse outcome than a port that reads as text.

  An unparseable timestamp omits "time" and records time_raw. HEC then applies
  index time, and the unreadable value stays visible instead of becoming a
  plausible wrong number.
"""

from . import timeparse

# Fields Splunk's CIM treats as numeric. A value that will not convert stays
# as text under the same name rather than being dropped or zeroed.
NUMERIC_FIELDS = frozenset({
    "src_port", "dest_port", "bytes_in", "bytes_out", "bytes",
    "duration", "packets", "packets_in", "packets_out", "severity_id",
    "response_time", "status", "http_status",
})

LOWERCASE_FIELDS = frozenset({"protocol", "action", "transport"})


def build(record, schema, source, fmt, extra=None, literals_seen=None):
    """Return the HEC envelope dict for one record.

    literals_seen, when given, collects (schema, field, value) for every
    mapping whose value was not a column in the record. The caller reports
    those once per file: a mistyped column name is indistinguishable from an
    intentional constant, and the difference only shows up as a field whose
    every value is the column's own name.
    """
    event = {}
    conversions = []

    for field, column in schema.cim.items():
        if field == "time":
            continue
        present = isinstance(column, str) and _resolve(record, column) is not _MISSING
        value = _literal_or_lookup(record, column, schema, field, literals_seen)
        if value is None or value == "":
            continue
        if field in NUMERIC_FIELDS:
            converted = _to_number(value)
            if converted is None:
                # A numeric field whose value is a non-numeric constant means
                # the mapping names a column the record does not have. Emitting
                # the column's own name as the value would be worse than
                # omitting the field, so omit it.
                if not present:
                    continue
                conversions.append(field)
            else:
                value = converted
        elif field in LOWERCASE_FIELDS and isinstance(value, str):
            value = value.lower()
        event[field] = value

    event["schema"] = schema.name
    event["connector_format"] = fmt
    if conversions:
        # Naming the fields that stayed as text keeps a type surprise
        # searchable rather than leaving it to be noticed on a chart.
        event["unconverted_numeric_fields"] = sorted(conversions)
    if extra:
        event.update(extra)

    envelope = {"event": event, "sourcetype": schema.sourcetype, "source": source}

    epoch = None
    if schema.time_field:
        raw_time = _literal_or_lookup(record, schema.time_field)
        epoch = timeparse.to_epoch(raw_time)
        if epoch is None and raw_time not in (None, ""):
            event["time_raw"] = raw_time
            event["time_parse_failed"] = True
    if epoch is not None:
        envelope["time"] = epoch

    if schema.index:
        envelope["index"] = schema.index
    return envelope


def build_unmatched(record, source, fmt, sourcetype):
    """Envelope for a record no schema claimed, kept rather than dropped."""
    event = {k: v for k, v in record.items() if v not in (None, "")}
    event["schema"] = "unmatched"
    event["schema_match"] = "none"
    event["connector_format"] = fmt
    return {"event": event, "sourcetype": sourcetype, "source": source}


_MISSING = object()


def _resolve(record, column):
    """The record's value for a mapping name, or _MISSING.

    A dotted name walks nested objects, which is how the JSON schemas address
    source.ip and destination.port. A flat key wins over the walk so a column
    whose own name contains a dot still resolves.
    """
    if column in record:
        return record[column]
    if "." not in column:
        return _MISSING
    value = record
    for segment in column.split("."):
        if not isinstance(value, dict) or segment not in value:
            return _MISSING
        value = value[segment]
    return value


def _literal_or_lookup(record, column, schema=None, field=None, literals_seen=None):
    """A mapping value naming a field is a reference; anything else is a
    constant.

    schemas.yaml writes protocol: "modbus" for a fixed value and
    protocol: proto for a reference, and YAML strips the quotes from both, so
    the only thing left to test is whether the record holds that name. A
    missing field and an intended constant are the same case here, and the
    caller learns which through literals_seen so a typo is reportable rather
    than silently a constant.
    """
    if column is None:
        return None
    if isinstance(column, (list, dict)):
        return column
    if not isinstance(column, str):
        return column
    value = _resolve(record, column)
    if value is not _MISSING:
        return value
    if literals_seen is not None and schema is not None:
        literals_seen.add((schema.name, field, column))
    return column


def _to_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return None
