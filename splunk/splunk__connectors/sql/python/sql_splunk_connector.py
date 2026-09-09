#!/usr/bin/env python3
"""
SQL to Splunk HEC.

Reads database tables through core/, so offsets, schema matching, time coercion,
retry and framing are the same as every other connector. See ../../README.md
for the delivery contract.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core import runner  # noqa: E402
from core.sources import SqlSource  # noqa: E402


def main():
    return runner.main(
        fmt="sql",
        log_dir_var="SQL_LOG_DIR",
        extension=".sql",
        source_factory=lambda config, schemas, log: SqlSource(config, schemas, log),
        sink="splunk",
    )


if __name__ == "__main__":
    sys.exit(main())
