#!/usr/bin/env python3
"""JSON Lines to Splunk HEC.

Tails newline-delimited JSON in JSON_LOG_DIR, maps each object through
schemas.yaml and posts it to HEC. The loop, offsets, retry and HEC framing are
shared with the other formats in core/.

Environment, beyond the shared settings in core/config.py:

  JSON_LOG_DIR      directory to tail                 /var/log/json_data
  SCHEMAS_FILE      schema definitions                /app/schemas.yaml
  SPLUNK_HEC_URL    collector endpoint                (required, no default)
  SPLUNK_TOKEN      HEC token                         (required)
  STATE_PATH        offset file                       /var/lib/connector/offsets.json

One object per line. A line that will not parse is forwarded carrying its own
text under _raw with _parse_error set, so malformed input is searchable rather
than a gap in the timeline.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core import runner  # noqa: E402
from core.parsers import JsonLinesParser  # noqa: E402


def main():
    return runner.main(
        fmt="json",
        log_dir_var="JSON_LOG_DIR",
        extension=".json",
        parser_factory=lambda config: JsonLinesParser(),
    )


if __name__ == "__main__":
    sys.exit(main())
