#!/usr/bin/env python3
"""Emit a GitHub Actions build matrix. Usage: discover.py <mode> [items...]"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ci"))
from dockerfile_targets import entries, select  # noqa: E402


def main(argv):
    mode = argv[0] if argv else "all"
    items = argv[1:]
    matrix_entries = entries(select(mode, items))
    print(f"matrix={json.dumps({'include': matrix_entries})}")
    print(f"has_targets={'true' if matrix_entries else 'false'}")


if __name__ == "__main__":
    main(sys.argv[1:])
