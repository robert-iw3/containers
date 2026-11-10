#!/usr/bin/env python3
"""Remove pandoc's per-heading bookmarks from a .docx, in place.

Pandoc emits one bookmark per heading so a table-of-contents field can link to
it. These documents carry no such field: Word navigates them by heading style.
The bookmarks therefore link to nothing, and some editors list every one of them
in a navigation pane the reader did not ask for.

Runs inside the documentation renderer image, which carries python3, so the
build host is not asked for one.
"""
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


def strip(path: Path) -> int:
    if not zipfile.is_zipfile(path):
        raise SystemExit(f"not a .docx (no zip container): {path}")
    tmp = Path(tempfile.mkdtemp())
    try:
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        doc = tmp / "word" / "document.xml"
        s = doc.read_text(encoding="utf-8")
        before = s.count("<w:bookmarkStart")
        # _GoBack is Word's own "return to last edit" mark; leaving it is
        # harmless and removing it makes no difference to the reader.
        s = re.sub(r'<w:bookmarkStart[^>]*w:name="(?!_GoBack)[^"]*"[^>]*/>', "", s)
        s = re.sub(r"<w:bookmarkEnd[^>]*/>", "", s)
        doc.write_text(s, encoding="utf-8")
        rebuilt = path.with_suffix(".rebuilt")
        with zipfile.ZipFile(rebuilt, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(tmp.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(tmp).as_posix())
        shutil.move(str(rebuilt), str(path))
        return before - s.count("<w:bookmarkStart")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: strip-docx-bookmarks.py <file.docx> [...]")
    for arg in sys.argv[1:]:
        strip(Path(arg))
