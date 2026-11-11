#!/usr/bin/env python3
"""Remove the monitor inputs that validation rounds leave behind.

Every round stages its batch under its own path and adds a monitor stanza
for it. After a campaign that is dozens of stanzas pointing at files that
have already been read: they do no harm on their own, but they outlive the
data they loaded and they make the real inputs hard to find.

    ./bin/prune-round-inputs.py --container epo-uat-uf
    ./bin/prune-round-inputs.py --file /path/to/inputs.conf --dry-run
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_CONF = "/opt/splunkforwarder/etc/apps/sigma_lab_inputs/local/inputs.conf"
MARKER = "/lab-logs/validate/"


def prune(text: str, marker: str):
    """Drop whole stanzas whose monitor path contains the marker."""
    out, buf, cur, dropped = [], [], None, []
    for line in text.splitlines():
        st = line.strip()
        if st.startswith("[monitor://"):
            if cur is None:
                out.extend(buf)
            elif marker in cur:
                dropped.append(cur)
            else:
                out.extend(buf)
            cur, buf = st, [line]
            continue
        (buf if cur is not None else out).append(line)
    if cur is None:
        out.extend(buf)
    elif marker in cur:
        dropped.append(cur)
    else:
        out.extend(buf)
    return "\n".join(out).rstrip() + "\n", dropped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--container", default=None)
    ap.add_argument("--file", default=DEFAULT_CONF)
    ap.add_argument("--marker", default=MARKER)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.container:
        text = subprocess.run(
            ["podman", "exec", args.container, "cat", args.file],
            capture_output=True, text=True).stdout
    else:
        text = Path(args.file).read_text()
    if not text:
        print(f"  nothing read from {args.file}")
        return 0

    new, dropped = prune(text, args.marker)
    print(f"  {len(dropped)} round input stanza(s) to remove")
    for d in dropped[:6]:
        print(f"    {d[11:-1].split('/')[-1]}")
    if args.dry_run:
        print("  dry run; nothing was changed")
        return 0
    if not dropped:
        return 0

    tmp = Path("/tmp/_pruned_inputs.conf")
    tmp.write_text(new)
    if args.container:
        subprocess.run(["podman", "cp", str(tmp), f"{args.container}:{args.file}"])
        acct = subprocess.run(["podman", "exec", args.container, "sh", "-c",
                               "ps -o user= -p 1"], capture_output=True,
                              text=True).stdout.strip() or "ansible"
        subprocess.run(["podman", "exec", "-u", "root", args.container,
                        "chown", f"{acct}:{acct}", args.file])
    else:
        Path(args.file).write_text(new)
    print(f"  {args.file} rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
