"""
Write the fixtures the connectors are tested against.

Two families, for two different questions.

  generic_*   matches the shipped schemas.yaml, so a connector has no excuse
              for failing it. Anything that breaks here is broken outright.

  trellix_*   the CSV contract proved against a production ePO export. Its
              columns, its ISO 8601 timestamps and its CRLF line endings are
              what a PowerShell exporter actually emits, so it is the case
              that decides whether a connector works on real input rather
              than on input shaped like the connector's assumptions.

Both carry rows chosen to break things: an unclassifiable row, an empty
numeric, a quoted field holding the delimiter, an embedded newline, and
non-ASCII. A fixture of well-formed rows agrees with every bug below it.

The expected outcome of each row is recorded in expectations.json rather than
hardcoded in the checks, so a fixture change cannot quietly disagree with the
assertions that read it.
"""

import csv
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fixtures")

# The events feed of the proven contract. Provenance:
#   trellix/implementation/deploy-mvp/sql/SP_ExportEventsWithAgentContext.sql
#   via epo_splunk_app/lab/fixtures/contract.json (sha256 37d6c613...)
# Vendored rather than read across repositories: the contract is a surface to
# pin, not a file to depend on at run time.
TRELLIX_EVENT_COLUMNS = [
    "record_id", "detected", "received", "event_time_local", "ingest_lag_seconds",
    "module", "product", "product_version", "engine_version", "content_version",
    "detection_method", "server_id", "event_id", "signature", "threat_type",
    "threat_category", "severity_id", "threat_handled", "action_raw", "action",
    "dest", "dest_ip", "dest_ipv6", "dest_mac", "dest_port", "dest_protocol",
    "user", "file_name", "dest_process", "src", "src_ip", "src_ipv6", "src_mac",
    "src_process", "src_user", "src_url", "reporter_host", "reporter_ip",
    "reporter_ipv6", "reporter_mac", "dest_ip_raw", "src_ip_raw", "agent_guid",
    "agent_node_name", "agent_last_comm", "agent_tags", "os_domain",
    "os_logged_user", "system_desc", "system_match",
]


def trellix_row(record_id, module, signature, action, **over):
    row = {c: "" for c in TRELLIX_EVENT_COLUMNS}
    row.update(
        record_id=str(record_id),
        detected=f"2026-09-0{1 + record_id % 8}T14:2{record_id % 6}:1{record_id % 9}.{record_id % 999:03d}Z",
        received=f"2026-09-0{1 + record_id % 8}T14:2{record_id % 6}:2{record_id % 9}.000Z",
        event_time_local=f"2026-09-0{1 + record_id % 8}T09:2{record_id % 6}:1{record_id % 9}.000Z",
        ingest_lag_seconds="11",
        module=module,
        product="ENDPOINT SECURITY",
        product_version="10.7.0",
        engine_version="6700.9800",
        content_version="5432",
        server_id="EPO-PRIMARY",
        event_id=str(1027 + record_id),
        signature=signature,
        severity_id="3",
        threat_handled="1",
        action_raw=action.upper().replace("-", "_"),
        action=action,
        dest=f"WKS-{record_id:04d}",
        dest_ip=f"10.20.{record_id % 256}.{(record_id * 7) % 254 + 1}",
        dest_mac=f"00:1a:2b:{record_id % 100:02d}:c4:d5",
        dest_port="443",
        user="CORP\\\\jdoe",
        agent_guid=f"{record_id:08X}-1111-2222-3333-444455556666",
        agent_node_name=f"WKS-{record_id:04d}",
        agent_last_comm="2026-09-07T11:00:00.000Z",
        os_domain="CORP",
        system_match="exact",
    )
    row.update(over)
    return row


def write_csv(path, columns, rows, newline="\r\n", delimiter=","):
    """Write with CRLF by default - a Windows StreamWriter emits CRLF, and the
    exporter that produces the real feed runs on Windows."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, delimiter=delimiter, lineterminator=newline)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(buf.getvalue())


def main():
    os.makedirs(OUT, exist_ok=True)
    expectations = {}

    # --- Trellix contract, 50 columns, CRLF, ISO 8601 timestamps -----------
    rows = [
        trellix_row(1, "endpoint", "T1059.001_PowerShell_Encoded_Command", "blocked",
                    threat_type="malware", threat_category="trojan",
                    detection_method="on-access", file_name="powershell.exe"),
        trellix_row(2, "endpoint", "T1003.001_OS_Credential_Dumping_LSASS", "would-block",
                    threat_type="malware", threat_category="credential-access",
                    detection_method="exploit-prevention", file_name="lsass.exe"),
        # A DLP row: the channel is detection_method, the dotted classification
        # is threat_category. Reversing those two renders the wrong dimension.
        trellix_row(3, "dlp", "DLP_Rule_PII_Egress", "blocked",
                    threat_type="dlp", threat_category="dlp.classification.pii",
                    detection_method="Removable Media",
                    file_name="q3-customer-list.xlsx"),
        # Quoted field holding the delimiter, and a non-ASCII path.
        trellix_row(4, "endpoint", "T1566.001_Spearphishing_Attachment", "quarantined",
                    threat_type="malware", threat_category="trojan",
                    detection_method="on-access",
                    file_name='C:\\Users\\Public\\facturación, final.docx',
                    system_desc='Reception desk, lobby "A"'),
        # Empty numerics. int("") raises, and a connector that drops the row on
        # that loses an event that Splunk would have taken.
        trellix_row(5, "endpoint", "T1071.001_Web_Protocol_C2", "allowed",
                    threat_type="web", threat_category="c2",
                    detection_method="web-control", dest_port="", severity_id=""),
        # Unclassifiable: module is neither dlp nor endpoint. Must be visible
        # as a refusal, never dropped in silence.
        trellix_row(6, "unmapped-module", "Unknown_Signature", "none",
                    threat_type="", threat_category=""),
    ]
    write_csv(os.path.join(OUT, "trellix_events.csv"), TRELLIX_EVENT_COLUMNS, rows)
    expectations["trellix_events.csv"] = {
        "rows": len(rows),
        "classifiable": 5,
        "unclassifiable": 1,
        "line_ending": "CRLF",
        "time_field": "detected",
        "time_format": "ISO 8601, NOT epoch",
        "note": "HEC rejects a non-numeric time field with code 6, losing the whole batch.",
    }

    # --- Generic, matching the shipped schemas.yaml ------------------------
    generic_cols = [
        "event_type", "timestamp", "id", "category", "source_ip", "source_port",
        "dest_ip", "dest_port", "protocol", "bytes_sent", "bytes_received", "action",
    ]
    generic = [
        {"event_type": "network_event", "timestamp": "1767225600", "id": "e1",
         "category": "network", "source_ip": "10.0.0.1", "source_port": "51000",
         "dest_ip": "10.0.0.2", "dest_port": "443", "protocol": "TCP",
         "bytes_sent": "1200", "bytes_received": "900", "action": "allowed"},
        {"event_type": "network_event", "timestamp": "1767225601", "id": "e2",
         "category": "network", "source_ip": "10.0.0.3", "source_port": "",
         "dest_ip": "10.0.0.4", "dest_port": "", "protocol": "UDP",
         "bytes_sent": "0", "bytes_received": "0", "action": "blocked"},
        {"event_type": "network_event", "timestamp": "1767225602", "id": "e3,with,commas",
         "category": "network, industrial", "source_ip": "10.0.0.5",
         "source_port": "52000", "dest_ip": "10.0.0.6", "dest_port": "502",
         "protocol": "TCP", "bytes_sent": "64", "bytes_received": "64",
         "action": "allowed"},
        {"event_type": "flow", "timestamp": "1767225603", "id": "e4",
         "category": "network", "source_ip": "10.0.0.7", "source_port": "53000",
         "dest_ip": "10.0.0.8", "dest_port": "80", "protocol": "TCP",
         "bytes_sent": "10", "bytes_received": "10", "action": "allowed"},
        {"event_type": "no_such_type", "timestamp": "1767225604", "id": "e5",
         "category": "", "source_ip": "", "source_port": "", "dest_ip": "",
         "dest_port": "", "protocol": "", "bytes_sent": "", "bytes_received": "",
         "action": ""},
    ]
    write_csv(os.path.join(OUT, "generic_network.csv"), generic_cols, generic, newline="\n")
    expectations["generic_network.csv"] = {
        "rows": len(generic),
        # e4 is schema "flow", whose schema_key is also event_type; only e5 has
        # no matching schema at all.
        "classifiable": 4,
        "unclassifiable": 1,
        "line_ending": "LF",
        "time_field": "timestamp",
        "time_format": "epoch seconds",
    }

    # Same rows, semicolon-delimited: proves delimiter handling is real rather
    # than a comma check that happens to pass.
    write_csv(os.path.join(OUT, "semicolon.csv"), generic_cols, generic,
              newline="\n", delimiter=";")
    expectations["semicolon.csv"] = dict(expectations["generic_network.csv"], delimiter=";")

    # --- NDJSON for the json connector ------------------------------------
    # Nested, because the shipped JSON schemas address source.ip and
    # destination.port. A flat fixture agrees with a mapping that cannot walk
    # a dotted path, so it proves nothing.
    def nest(row):
        return {
            "event_type": row["event_type"],
            "timestamp": row["timestamp"],
            "id": row["id"],
            "category": row["category"],
            "source": {"ip": row["source_ip"], "port": row["source_port"]},
            "destination": {"ip": row["dest_ip"], "port": row["dest_port"]},
            "protocol": row["protocol"],
            "bytes_sent": row["bytes_sent"],
            "bytes_received": row["bytes_received"],
            "action": row["action"],
        }

    with open(os.path.join(OUT, "generic_events.json"), "w", encoding="utf-8") as handle:
        for row in generic:
            handle.write(json.dumps(nest(row)) + "\n")
    expectations["generic_events.json"] = dict(expectations["generic_network.csv"])
    expectations["generic_events.json"].pop("delimiter", None)
    expectations["generic_events.json"]["shape"] = "nested (source.ip, destination.port)"

    # --- XML: sibling record elements, one event each ----------------------
    # Includes an entity declaration. The parser runs with entity resolution
    # off, so this must arrive as inert text rather than expanded.
    xml_rows = "\n".join(
        f"  <record><event_type>{r['event_type']}</event_type>"
        f"<timestamp>{r['timestamp']}</timestamp><id>{r['id']}</id>"
        f"<source_ip>{r['source_ip']}</source_ip>"
        f"<source_port>{r['source_port']}</source_port>"
        f"<dest_ip>{r['dest_ip']}</dest_ip>"
        f"<dest_port>{r['dest_port']}</dest_port>"
        f"<protocol>{r['protocol']}</protocol>"
        f"<action>{r['action']}</action></record>"
        for r in generic
    )
    with open(os.path.join(OUT, "generic_events.xml"), "w", encoding="utf-8") as handle:
        handle.write(xml_rows + "\n")
    expectations["generic_events.xml"] = {
        "rows": len(generic),
        "classifiable": 4,
        "unclassifiable": 1,
        "line_ending": "LF",
        "time_field": "timestamp",
        "time_format": "epoch seconds",
        "shape": "sibling <record> elements",
    }

    with open(os.path.join(OUT, "expectations.json"), "w", encoding="utf-8") as handle:
        json.dump(expectations, handle, indent=2, sort_keys=True)

    for name, meta in sorted(expectations.items()):
        path = os.path.join(OUT, name)
        print(f"{name:26s} {os.path.getsize(path):7d} bytes  "
              f"{meta['rows']} rows ({meta['classifiable']} classifiable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
