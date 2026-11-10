#!/usr/bin/env python3
"""Make a rendered .docx a pure function of its source.

WHY THIS EXISTS

Rendering the same markdown twice produced two files with different sha256 sums.
Every content part was byte-identical; what differed was the build clock, in the
zip entry timestamps and in docProps/core.xml's created and modified dates. That
is enough to defeat a hash comparison, and this package is delivered through a
media door where hashes are how a file is checked.

The timestamp used is SOURCE_DATE_EPOCH when it is set, which is the convention
other reproducible builds use, and otherwise the modification time of the markdown
the document was rendered from. Either way the same source gives the same bytes,
and changing the source changes them.

    ./normalize-docx.py docs/03-user-guide.docx
    SOURCE_DATE_EPOCH=1700000000 ./normalize-docx.py docs/*.docx
"""
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path


def stamp_for(docx: Path) -> int:
    env = os.environ.get("SOURCE_DATE_EPOCH")
    if env:
        return int(env)
    md = docx.with_suffix(".md")
    if md.exists():
        return int(md.stat().st_mtime)
    return int(docx.stat().st_mtime)


def normalize(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise SystemExit(f"not a .docx: {path}")
    epoch = stamp_for(path)
    # Zip stores two-second resolution and cannot represent anything before 1980.
    dt = time.gmtime(max(epoch, 315532800))
    zt = (dt.tm_year, dt.tm_mon, dt.tm_mday, dt.tm_hour, dt.tm_min, dt.tm_sec // 2 * 2)
    iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", dt)

    tmp = Path(tempfile.mkdtemp())
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            z.extractall(tmp)
        core = tmp / "docProps" / "core.xml"
        if core.exists():
            s = core.read_text(encoding="utf-8")
            s = re.sub(r"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:)",
                       lambda m: m.group(1) + iso + m.group(2), s)
            core.write_text(s, encoding="utf-8")

        rebuilt = path.with_suffix(".normalized")
        # Entry order is preserved: a reader that trusts the original ordering,
        # and any tool diffing the two archives, should see only the dates change.
        with zipfile.ZipFile(rebuilt, "w", zipfile.ZIP_DEFLATED) as z:
            for name in names:
                f = tmp / name
                if not f.is_file():
                    continue
                info = zipfile.ZipInfo(name, date_time=zt)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, f.read_bytes())
        shutil.move(str(rebuilt), str(path))
        # The file's own mtime is deliberately left at the build time. It is not
        # part of the archive's bytes, so it does not affect the hash, and
        # bin/build-package.sh compares it against the markdown's to catch a
        # document whose source moved on. Stamping it back to the source's time
        # made the source fractionally newer at sub-second precision and the
        # packager refused to write an archive.
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: normalize-docx.py <file.docx> [...]")
    for a in sys.argv[1:]:
        normalize(Path(a))
