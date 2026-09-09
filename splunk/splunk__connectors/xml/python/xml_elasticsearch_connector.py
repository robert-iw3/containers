#!/usr/bin/env python3
"""XML to Elasticsearch.

The same tailing, offsets, schema matching and time coercion as the Splunk
connector; only the destination differs. Documents go to the _bulk API.

Environment, beyond the shared settings in core/config.py:

  XML_LOG_DIR       directory to tail                 /var/log/xml_data
  XML_RECORD_ELEM   element name holding one event    (any top-level element)
  SCHEMAS_FILE      schema definitions                /app/schemas.yaml
  ES_HOST           cluster URL                       http://localhost:9200
  ES_INDEX          destination index                 xml-logs
  ES_USER           basic auth user, optional
  ES_PASSWORD       basic auth password, optional
  STATE_PATH        offset file                       /var/lib/connector/offsets.json
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core import runner  # noqa: E402
from core.parsers import XmlParser  # noqa: E402


def main():
    return runner.main(
        fmt="xml",
        log_dir_var="XML_LOG_DIR",
        extension=".xml",
        parser_factory=lambda config: XmlParser(
            record_element=os.getenv("XML_RECORD_ELEM") or None
        ),
        sink="elasticsearch",
    )


if __name__ == "__main__":
    sys.exit(main())
