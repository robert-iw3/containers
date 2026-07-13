#!/usr/bin/env python3
"""Hadoop Streaming reducer: sum the per-(source::level) counts.

Streaming feeds the reducer key-sorted lines, so we accumulate while the key is
unchanged. Output: `source::level\t<count>` -> the curated log-analytics rollup.
"""

import sys


def main() -> None:
    current = None
    total = 0
    for line in sys.stdin:
        key, _, value = line.rstrip("\n").partition("\t")
        if key != current:
            if current is not None:
                sys.stdout.write(f"{current}\t{total}\n")
            current = key
            total = 0
        total += int(value or 0)
    if current is not None:
        sys.stdout.write(f"{current}\t{total}\n")


if __name__ == "__main__":
    main()
