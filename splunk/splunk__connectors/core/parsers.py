"""
Per-format record extraction.

A parser turns a byte chunk into (records, consumed_bytes). consumed_bytes is
the length of the prefix that yielded whole records, so a chunk that ends
mid-record advances only as far as the last complete one and the remainder is
re-read on the next pass. Returning the full chunk length instead is how a
tailer loses the record straddling a boundary.

Chunks are read as bytes and decoded here. The CSV module needs text, and
decoding a chunk that splits a multi-byte character is a decode error rather
than a lost byte, so the split is repaired before parsing.
"""

import csv
import io
import json

from .schemas import SchemaError


def _decode(chunk):
    """Text, plus the bytes that could not be decoded because the chunk cut a
    multi-byte character in half. Those bytes go back for the next read."""
    for trim in range(0, 4):
        end = len(chunk) - trim
        try:
            return chunk[:end].decode("utf-8"), trim
        except UnicodeDecodeError:
            continue
    return chunk.decode("utf-8", errors="replace"), 0


def _whole_lines(text):
    """Text up to the last newline, and how many characters that is.

    A chunk almost never ends on a record boundary, so the trailing partial
    line is left for the next read.
    """
    cut = text.rfind("\n")
    if cut < 0:
        return "", 0
    return text[: cut + 1], cut + 1


class CsvParser:
    """Delimited text with a header row.

    The header is captured once, when reading from offset 0, and reused for
    every later chunk of that file. A resumed read starts mid file where no
    header line exists, and csv.DictReader given a chunk from there treats the
    first data row as the header - one row lost and every field after it keyed
    by the wrong name.
    """

    extension = ".csv"

    def __init__(self, delimiter=","):
        self.delimiter = delimiter

    def sniff_header(self, chunk):
        text, _ = _decode(chunk)
        line = text.split("\n", 1)[0].strip("\r")
        if not line:
            return None, 0
        # The header's own bytes are consumed; data starts after it.
        consumed = len(line.encode("utf-8")) + self._newline_width(text, len(line))
        reader = csv.reader(io.StringIO(line), delimiter=self.delimiter)
        try:
            columns = next(reader)
        except (csv.Error, StopIteration):
            return None, 0
        return columns, consumed

    @staticmethod
    def _newline_width(text, index):
        if text[index:index + 2] == "\r\n":
            return 2
        if text[index:index + 1] in ("\n", "\r"):
            return 1
        return 0

    def parse(self, chunk, header):
        if header is None:
            raise SchemaError("CSV chunk parsed without a header")
        text, undecoded = _decode(chunk)
        body, consumed_chars = _whole_lines(text)
        if not body:
            return [], 0
        reader = csv.DictReader(
            io.StringIO(body), fieldnames=header, delimiter=self.delimiter
        )
        records = []
        for row in reader:
            # restkey/restval land as None for a short or long row; drop the
            # unnamed overflow and keep the row rather than the whole chunk.
            row.pop(None, None)
            records.append({k: ("" if v is None else v) for k, v in row.items()})
        return records, len(body.encode("utf-8"))


class JsonLinesParser:
    """One JSON object per line."""

    extension = ".json"

    def sniff_header(self, chunk):
        return None, 0

    def parse(self, chunk, header):
        text, _ = _decode(chunk)
        body, _ = _whole_lines(text)
        if not body:
            return [], 0
        records = []
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                # A malformed line is skipped with its content preserved, so a
                # parse failure is searchable instead of being a gap.
                records.append({"_parse_error": "invalid JSON", "_raw": line[:2000]})
                continue
            records.append(obj if isinstance(obj, dict) else {"value": obj})
        return records, len(body.encode("utf-8"))


class XmlParser:
    """A sequence of sibling elements, each one event.

    Entity resolution and huge_tree are off. An XML connector reads files it
    did not write, and libxml2 with entities enabled will fetch external
    references and expand nested entities on request of the document.
    """

    extension = ".xml"

    def __init__(self, record_element=None):
        self.record_element = record_element

    def sniff_header(self, chunk):
        return None, 0

    def parse(self, chunk, header):
        from lxml import etree

        text, _ = _decode(chunk)
        # Wrap in a synthetic root: a chunk of sibling elements is not a
        # well-formed document, and the real root may be split across chunks.
        cut = text.rfind(">")
        if cut < 0:
            return [], 0
        body = text[: cut + 1]

        parser = etree.XMLParser(
            resolve_entities=False, no_network=True, huge_tree=False, recover=True
        )
        try:
            root = etree.fromstring(f"<connectorRoot>{body}</connectorRoot>".encode("utf-8"), parser)
        except etree.XMLSyntaxError:
            return [], 0
        if root is None:
            return [], 0

        records = []
        for element in root:
            if self.record_element and etree.QName(element).localname != self.record_element:
                continue
            record = {"_element": etree.QName(element).localname}
            ns = etree.QName(element).namespace
            if ns:
                record["_namespace"] = ns
            for key, value in element.attrib.items():
                record[etree.QName(key).localname] = value
            for child in element.iter():
                if child is element:
                    continue
                if child.text and child.text.strip():
                    record[etree.QName(child).localname] = child.text.strip()
            records.append(record)

        consumed = len(body.encode("utf-8")) if records else 0
        return records, consumed
