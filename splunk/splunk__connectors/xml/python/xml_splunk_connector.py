#!/usr/bin/env python3
"""XML to Splunk HEC.

Tails XML in XML_LOG_DIR, treats each top-level element as one event, maps it
through schemas.yaml and posts it to HEC. The loop, offsets, retry and HEC
framing are shared with the other formats in core/.

Environment, beyond the shared settings in core/config.py:

  XML_LOG_DIR       directory to tail                 /var/log/xml_data
  XML_RECORD_ELEM   element name holding one event    (any top-level element)
  SCHEMAS_FILE      schema definitions                /app/schemas.yaml
  SPLUNK_HEC_URL    collector endpoint                (required, no default)
  SPLUNK_TOKEN      HEC token                         (required)
  STATE_PATH        offset file                       /var/lib/connector/offsets.json

The parser runs with entity resolution and network access disabled, and
without huge_tree. A connector reads files it did not write, and libxml2 with
entities enabled will fetch external references and expand nested entities
because the document asked it to.

Elements are matched against schemas by name: a schema is selected by
schema_key/schema_value against the flattened element, so _element carries the
element's local name and can be used as the key.
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
    )


if __name__ == "__main__":
    sys.exit(main())
