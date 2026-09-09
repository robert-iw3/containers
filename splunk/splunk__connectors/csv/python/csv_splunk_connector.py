#!/usr/bin/env python3
"""CSV to Splunk HEC.

Tails delimited files in CSV_LOG_DIR, maps each row through schemas.yaml and
posts it to HEC. The loop, offsets, retry and HEC framing are shared with the
other formats in core/; this file supplies the parser and the names of the
format's environment variables.

Environment, beyond the shared settings in core/config.py:

  CSV_LOG_DIR       directory to tail                 /var/log/csv_data
  CSV_DELIMITER     single character                  ,
  SCHEMAS_FILE      schema definitions                /app/schemas.yaml
  SPLUNK_HEC_URL    collector endpoint                (required, no default)
  SPLUNK_TOKEN      HEC token                         (required)
  STATE_PATH        offset file                       /var/lib/connector/offsets.json

The delimiter is configuration, not a guess. Sniffing it from file content
returns a comma for any file that contains one anywhere, which is nearly all
of them, so a semicolon-delimited export parses as a single column and every
mapped field comes back empty.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core import runner  # noqa: E402
from core.parsers import CsvParser  # noqa: E402


def main():
    return runner.main(
        fmt="csv",
        log_dir_var="CSV_LOG_DIR",
        extension=".csv",
        parser_factory=lambda config: CsvParser(delimiter=config.delimiter),
    )


if __name__ == "__main__":
    sys.exit(main())
