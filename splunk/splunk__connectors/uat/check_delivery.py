"""
Assert what actually reached the collector.

A delivered count says events arrived. It does not say the right values
arrived under the right names, which is the failure that survives a green
test and shows up as a plausible, wrong dashboard. These checks read the
accepted events back and test the content.

    python3 check_delivery.py <events.jsonl> <case-name>
"""

import json
import sys

PASS, FAIL = 0, 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"    ok    {name}")
    else:
        FAIL += 1
        print(f"    FAIL  {name}" + (f" - {detail}" if detail else ""))


def load(path):
    events = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line)["received"])
    return events


def common(events, expect_total, expect_unmatched):
    check(f"delivered {expect_total} events", len(events) == expect_total, f"got {len(events)}")

    unmatched = [e for e in events if e["event"].get("schema_match") == "none"]
    check(
        f"{expect_unmatched} unmatched record(s) forwarded, not dropped",
        len(unmatched) == expect_unmatched,
        f"got {len(unmatched)}",
    )

    # HEC rejects a non-numeric time, and the rejection takes the whole batch.
    bad_time = [e for e in events if "time" in e and not isinstance(e["time"], (int, float))]
    check("every time field is numeric", not bad_time, f"{len(bad_time)} non-numeric")

    # An empty CSV cell must be absent, not "". Splunk's field="" matches
    # nothing, so an empty string makes a search quietly wrong.
    empties = [
        (e["event"].get("schema"), k)
        for e in events
        for k, v in e["event"].items()
        if v == ""
    ]
    check("no field was delivered as an empty string", not empties, str(empties[:5]))

    check(
        "every event carries a sourcetype",
        all(e.get("sourcetype") for e in events),
    )


def trellix(events):
    by_id = {}
    for envelope in events:
        event = envelope["event"]
        key = event.get("event_id") or event.get("schema_match")
        by_id.setdefault(str(key), []).append(envelope)

    check("no event delivered twice", all(len(v) == 1 for v in by_id.values()),
          str({k: len(v) for k, v in by_id.items() if len(v) > 1}))

    # ISO 8601 with milliseconds, converted rather than passed through.
    times = [e["time"] for e in events if "time" in e]
    check("ISO 8601 timestamps converted to epoch", len(times) >= 5, f"got {len(times)}")
    check(
        "converted times land in 2026",
        all(1767225600 < t < 1798761600 for t in times),
        str(times[:3]),
    )

    dlp = [e for e in events if e["event"].get("schema") == "epo_dlp"]
    check("the DLP row matched the dlp schema", len(dlp) == 1, f"got {len(dlp)}")
    if dlp:
        event = dlp[0]["event"]
        # The channel is detection_method; threat_category holds the dotted
        # classification. Swapping them renders the wrong dimension.
        check(
            "DLP channel is detection_method='Removable Media'",
            event.get("detection_method") == "Removable Media",
            repr(event.get("detection_method")),
        )
        check(
            "DLP classification is category='dlp.classification.pii'",
            event.get("category") == "dlp.classification.pii",
            repr(event.get("category")),
        )

    # The row whose dest_port and severity_id are blank.
    blank = [e for e in events if e["event"].get("signature") == "T1071.001_Web_Protocol_C2"]
    check("the row with empty numerics still shipped", len(blank) == 1)
    if blank:
        check("its empty dest_port is absent, not zero", "dest_port" not in blank[0]["event"])

    nonascii = [
        e for e in events
        if "facturaci" in str(e["event"].get("file_name", ""))
    ]
    check("non-ASCII inside a quoted field survived", len(nonascii) == 1)
    if nonascii:
        check(
            "the quoted comma did not split the field",
            nonascii[0]["event"]["file_name"].endswith("final.docx"),
            repr(nonascii[0]["event"].get("file_name")),
        )

    unmatched = [e for e in events if e["event"].get("schema_match") == "none"]
    if unmatched:
        check(
            "the unmatched row kept its columns",
            unmatched[0]["event"].get("module") == "unmapped-module",
            repr(unmatched[0]["event"].get("module")),
        )
        check(
            "the unmatched row went to the unmatched sourcetype",
            unmatched[0]["sourcetype"] == "csv:unmatched",
            repr(unmatched[0].get("sourcetype")),
        )


def generic(events):
    ports = [e["event"]["dest_port"] for e in events if "dest_port" in e["event"]]
    check("numeric ports converted to integers", all(isinstance(p, int) for p in ports), str(ports))
    lowered = [e["event"].get("protocol") for e in events if "protocol" in e["event"]]
    check("protocol lowercased", all(p == p.lower() for p in lowered), str(lowered))
    check(
        "the row with commas in a quoted field kept them",
        any(e["event"].get("event_id") == "e3,with,commas" for e in events),
    )


def xml(events):
    ports = [e["event"]["dest_port"] for e in events if "dest_port" in e["event"]]
    check("numeric ports converted to integers", all(isinstance(p, int) for p in ports), str(ports))
    check(
        "each record element became one event",
        all(e["event"].get("connector_format") == "xml" for e in events),
    )


def db_rows(events):
    """The SQL and Parquet fixtures carry the same six ePO rows as the CSV one.

    A table or file is claimed whole, so every row is matched: there is no
    unmatched row here, and an unmatched TABLE is simply never polled.
    """
    check("no event delivered twice",
          len({e["event"].get("event_id") for e in events}) == len(events))
    times = [e["time"] for e in events if "time" in e]
    check("ISO 8601 timestamps converted to epoch", len(times) == len(events),
          f"{len(times)}/{len(events)}")
    check("converted times land in 2026",
          all(1767225600 < t < 1798761600 for t in times), str(times[:3]))

    dlp = [e for e in events if e["event"].get("detection_method") == "Removable Media"]
    check("the DLP row kept its channel in detection_method", len(dlp) == 1)
    if dlp:
        check("its classification is category='dlp.classification.pii'",
              dlp[0]["event"].get("category") == "dlp.classification.pii",
              repr(dlp[0]["event"].get("category")))

    # NULL numerics: the SQL analogue of a blank CSV cell.
    blank = [e for e in events
             if e["event"].get("signature") == "T1071.001_Web_Protocol_C2"]
    check("the row with NULL numerics still shipped", len(blank) == 1)
    if blank:
        check("its NULL dest_port is absent, not zero",
              "dest_port" not in blank[0]["event"])
        check("its NULL severity_id is absent, not zero",
              "severity_id" not in blank[0]["event"])

    nonascii = [e for e in events
                if "facturaci" in str(e["event"].get("file_name", ""))]
    check("non-ASCII survived the source", len(nonascii) == 1)

    ports = [e["event"]["dest_port"] for e in events if "dest_port" in e["event"]]
    check("ports are integers", all(isinstance(p, int) for p in ports), str(ports))


CASES = {
    "csv-generic": (5, 1, generic),
    "csv-trellix": (6, 1, trellix),
    "csv-semicolon": (5, 1, generic),
    "json-generic": (5, 1, generic),
    "xml-generic": (5, 1, xml),
    "sql-trellix": (6, 0, db_rows),
    "parquet-trellix": (6, 0, db_rows),
}


def main():
    path, case = sys.argv[1], sys.argv[2]
    expect_total, expect_unmatched, extra = CASES[case]
    events = load(path)
    common(events, expect_total, expect_unmatched)
    extra(events)
    print(f"    {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
