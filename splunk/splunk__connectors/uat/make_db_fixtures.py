"""
Write the SQLite and Parquet fixtures the sql and parquet cases read.

Neither source needs a server. SQLite is in the standard library and Parquet is
a file, so both connectors are testable end to end in the same harness the file
connectors use -- there is no reason for them to be the untested pair.

Both carry the ePO events contract, so a row that works through the CSV path
works through these too, and the same content assertions apply.
"""

import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The harness mounts the repository read-only, so inside a container these are
# written to a writable directory instead. SQLite opens its database
# read-write even for a SELECT, so it cannot live on the read-only mount.
OUT = os.environ.get("FIXTURE_DIR") or os.path.join(HERE, "fixtures")

COLUMNS = [
    ("record_id", "INTEGER"), ("detected", "TEXT"), ("module", "TEXT"),
    ("product", "TEXT"), ("detection_method", "TEXT"), ("event_id", "INTEGER"),
    ("signature", "TEXT"), ("threat_type", "TEXT"), ("threat_category", "TEXT"),
    ("severity_id", "INTEGER"), ("action", "TEXT"), ("dest", "TEXT"),
    ("dest_ip", "TEXT"), ("dest_port", "INTEGER"), ("user", "TEXT"),
    ("file_name", "TEXT"), ("agent_guid", "TEXT"),
]

# The same six rows as the CSV fixture: two endpoint, one DLP with the channel
# in detection_method, one non-ASCII, one with NULL numerics, one unmatched.
ROWS = [
    (1, "2026-09-01T14:20:11.001Z", "endpoint", "ENDPOINT SECURITY", "on-access",
     1028, "T1059.001_PowerShell_Encoded_Command", "malware", "trojan", 3,
     "blocked", "WKS-0001", "10.20.1.8", 443, "CORP\\jdoe", "powershell.exe",
     "00000001-1111-2222-3333-444455556666"),
    (2, "2026-09-02T14:21:12.002Z", "endpoint", "ENDPOINT SECURITY",
     "exploit-prevention", 1029, "T1003.001_OS_Credential_Dumping_LSASS",
     "malware", "credential-access", 3, "would-block", "WKS-0002", "10.20.2.15",
     443, "CORP\\jdoe", "lsass.exe", "00000002-1111-2222-3333-444455556666"),
    (3, "2026-09-03T14:22:13.003Z", "dlp", "DATA LOSS PREVENTION",
     "Removable Media", 1030, "DLP_Rule_PII_Egress", "dlp",
     "dlp.classification.pii", 3, "blocked", "WKS-0003", "10.20.3.22", 443,
     "CORP\\jdoe", "q3-customer-list.xlsx", "00000003-1111-2222-3333-444455556666"),
    (4, "2026-09-04T14:23:14.004Z", "endpoint", "ENDPOINT SECURITY", "on-access",
     1031, "T1566.001_Spearphishing_Attachment", "malware", "trojan", 3,
     "quarantined", "WKS-0004", "10.20.4.29", 443, "CORP\\jdoe",
     "C:\\Users\\Public\\facturaci\u00f3n, final.docx",
     "00000004-1111-2222-3333-444455556666"),
    # NULL numerics: the SQL analogue of a blank CSV cell.
    (5, "2026-09-05T14:24:15.005Z", "endpoint", "ENDPOINT SECURITY",
     "web-control", 1032, "T1071.001_Web_Protocol_C2", "web", "c2", None,
     "allowed", "WKS-0005", "10.20.5.36", None, "CORP\\jdoe", None,
     "00000005-1111-2222-3333-444455556666"),
    (6, "2026-09-06T14:25:16.006Z", "unmapped-module", "UNKNOWN", "", 1033,
     "Unknown_Signature", "", "", 3, "none", "WKS-0006", "10.20.6.43", 443,
     "CORP\\jdoe", None, "00000006-1111-2222-3333-444455556666"),
]


def write_sqlite(path):
    if os.path.exists(path):
        os.unlink(path)
    conn = sqlite3.connect(path)
    cols = ", ".join(f'"{n}" {t}' for n, t in COLUMNS)
    conn.execute(f"CREATE TABLE epo_events ({cols})")
    placeholders = ", ".join("?" for _ in COLUMNS)
    conn.executemany(f"INSERT INTO epo_events VALUES ({placeholders})", ROWS)
    conn.commit()
    # A second table nothing maps: the connector must not invent a schema for
    # it, and must not fail because of it either.
    conn.execute("CREATE TABLE unmapped_table (a TEXT)")
    conn.execute("INSERT INTO unmapped_table VALUES ('x')")
    conn.commit()
    conn.close()
    return len(ROWS)


def write_parquet(path):
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return None
    names = [n for n, _ in COLUMNS]
    columns = {n: [row[i] for row in ROWS] for i, n in enumerate(names)}
    table = pa.table(columns)
    # Two row groups, so a reader that only ever reads the first is caught.
    pq.write_table(table, path, row_group_size=3)
    return len(ROWS)


def main():
    os.makedirs(OUT, exist_ok=True)
    db = os.path.join(OUT, "epo_events.db")
    rows = write_sqlite(db)
    print(f"epo_events.db          {os.path.getsize(db):7d} bytes  {rows} rows, 1 mapped + 1 unmapped table")

    pqt = os.path.join(OUT, "epo_events.parquet")
    n = write_parquet(pqt)
    if n is None:
        print("epo_events.parquet     SKIPPED (pyarrow not installed)")
        return 1
    import pyarrow.parquet as pq
    groups = pq.ParquetFile(pqt).num_row_groups
    print(f"epo_events.parquet     {os.path.getsize(pqt):7d} bytes  {n} rows in {groups} row groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
