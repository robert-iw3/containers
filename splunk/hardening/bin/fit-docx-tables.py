#!/usr/bin/env python3
"""Widen a rendered .docx's over-narrow tables to the page's text width.

WHY THIS EXISTS

Pandoc's docx writer gives every table the same total width, 5.5 inches, and
divides it equally between the columns. It does that whatever the reference
document's page size says and whatever widths the pipe table's separator row
asks for. At two or three columns that is 2.75 or 1.83 inches each and reads
correctly, which is why no document in this project noticed. At seven columns it
is 0.79 inches, and the renderer breaks words across lines to fit: "Trelli" on
one line and "x Alert" on the next. The table is not wrong, it is unreadable,
and it passes every structural check because the XML is valid and every cell is
present.

WHAT IT DOES

A table whose columns are already comfortable is left exactly as it is, so the
existing documents keep the appearance they have. A table whose average column
falls below MIN_COMFORTABLE is rescaled to the full text width of its section,
with the columns weighted by how much text each one actually carries so a column
of one-word values does not take the same room as a column of sentences.

    ./fit-docx-tables.py docs/02-configuration-guide.docx
"""
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# EVERY TABLE IS FITTED TO THE TEXT WIDTH, not only the cramped ones. The first
# version of this widened a table only when its average column fell below a
# comfort threshold, which left a five-column table running the full width of a
# landscape page directly above a three-column one that stopped at 5.5 inches
# with 40 per cent of the page blank and its cells wrapped over five lines. Two
# table widths on one page read as a mistake, and the narrow one was wrapping
# text it had no need to wrap. One width throughout, columns weighted by content.
MIN_COMFORTABLE = None                 # retained for the guard below; unused
# No column may be squeezed under this, however little text it holds. Raised from
# 0.55in: at that floor the heading "Suppression" broke as "Suppressio" / "n",
# which is an ordinary English word and not an identifier anyone expects to split.
MIN_COLUMN = 0.80 * 1440
# Weighting is deliberately compressed: a cell with ten times the text of its
# neighbour needs more room, but not ten times more, or the short columns
# collapse and the long one becomes a paragraph.
def compress(n):
    return n ** 0.5


def text_width(doc: str) -> int:
    """The section's usable width, from the last sectPr in the body."""
    sect = re.findall(r"<w:sectPr\b.*?</w:sectPr>", doc, re.S)
    if not sect:
        return 0
    s = sect[-1]
    pg = re.search(r'<w:pgSz[^>]*w:w="(\d+)"', s)
    mar = re.search(r"<w:pgMar[^>]*>", s)
    if not (pg and mar):
        return 0
    left = re.search(r'w:left="(\d+)"', mar.group(0))
    right = re.search(r'w:right="(\d+)"', mar.group(0))
    if not (left and right):
        return 0
    return int(pg.group(1)) - int(left.group(1)) - int(right.group(1))


def refit(doc: str) -> tuple[str, int, int]:
    tw = text_width(doc)
    if tw <= 0:
        return doc, 0, 0

    out, pos, widened, seen = [], 0, 0, 0
    for m in re.finditer(r"<w:tbl>.*?</w:tbl>", doc, re.S):
        seen += 1
        tbl = m.group(0)
        grid = re.search(r"<w:tblGrid>.*?</w:tblGrid>", tbl, re.S)
        if not grid:
            continue
        cols = re.findall(r'<w:gridCol[^>]*w:w="(\d+)"[^>]*/?>', grid.group(0))
        n = len(cols)
        if n == 0:
            continue
        total = sum(int(c) for c in cols)
        if total >= tw:
            continue                          # already at or beyond the width

        # How much text each column carries, and the longest run in it that
        # cannot be broken. Total text alone is not enough: a column of one-digit
        # severities under the heading "alert.severity", or one holding
        # "ransomware_not_contained", carries little text and still needs room,
        # and a column narrower than its own longest token has that token split
        # across lines.
        weights = [0.0] * n
        longest = [1] * n
        for row in re.findall(r"<w:tr\b.*?</w:tr>", tbl, re.S):
            cells = re.findall(r"<w:tc>.*?</w:tc>", row, re.S)
            for i, cell in enumerate(cells[:n]):
                text = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", cell))
                weights[i] += len(text)
                for token in text.split():
                    if len(token) > longest[i]:
                        longest[i] = len(token)
        if not any(weights):
            weights = [1.0] * n

        # The two signals are combined rather than one chosen: the compressed
        # total decides the ordinary case, the longest token raises a column that
        # would otherwise be too narrow for a single word it must hold.
        # 0.5 was chosen by measuring this document's worst table at several
        # values. Higher and a column holding one long identifier starves the
        # prose columns beside it; lower and a heading like "alert.severity"
        # breaks across lines while the column beside it has room to spare. A
        # token of twenty-four characters does not fit any column of a
        # seven-column table, and is left to break.
        cw = [max(compress(w), lt * 0.5) or 1.0 for w, lt in zip(weights, longest)]
        floor_total = MIN_COLUMN * n
        spare = max(tw - floor_total, 0)
        scale = spare / sum(cw)
        new = [int(MIN_COLUMN + c * scale) for c in cw]
        new[-1] += tw - sum(new)                        # absorb the rounding

        new_grid = "<w:tblGrid>" + "".join(
            f'<w:gridCol w:w="{v}"/>' for v in new) + "</w:tblGrid>"
        tbl2 = tbl[:grid.start()] + new_grid + tbl[grid.end():]

        # Fixed layout, full width: an "auto" table is re-measured by the
        # renderer and the grid above becomes a suggestion it may ignore.
        tbl2 = re.sub(r"<w:tblW[^>]*/>", f'<w:tblW w:w="{tw}" w:type="dxa"/>', tbl2, count=1)
        tbl2 = re.sub(r"<w:tblLayout[^>]*/>", "", tbl2)
        tbl2 = tbl2.replace("<w:tblPr>", '<w:tblPr><w:tblLayout w:type="fixed"/>', 1)

        # Every cell's own width has to follow its column or Word re-measures.
        def fix_row(rm):
            row = rm.group(0)
            i = [0]
            def fix_cell(cm):
                cell = cm.group(0)
                idx = min(i[0], n - 1)
                span = re.search(r'<w:gridSpan[^>]*w:val="(\d+)"', cell)
                width = sum(new[idx:idx + int(span.group(1))]) if span else new[idx]
                i[0] += int(span.group(1)) if span else 1
                return re.sub(r"<w:tcW[^>]*/>", f'<w:tcW w:w="{width}" w:type="dxa"/>', cell, count=1)
            return re.sub(r"<w:tc>.*?</w:tc>", fix_cell, row, flags=re.S)

        tbl2 = re.sub(r"<w:tr\b.*?</w:tr>", fix_row, tbl2, flags=re.S)

        out.append(doc[pos:m.start()]); out.append(tbl2); pos = m.end()
        widened += 1

    out.append(doc[pos:])
    return "".join(out), widened, seen


def process(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise SystemExit(f"not a .docx: {path}")
    tmp = Path(tempfile.mkdtemp())
    try:
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        docxml = tmp / "word" / "document.xml"
        s = docxml.read_text(encoding="utf-8")
        s2, widened, seen = refit(s)
        if widened:
            docxml.write_text(s2, encoding="utf-8")
            rebuilt = path.with_suffix(".refit")
            with zipfile.ZipFile(rebuilt, "w", zipfile.ZIP_DEFLATED) as z:
                for f in sorted(tmp.rglob("*")):
                    if f.is_file():
                        z.write(f, f.relative_to(tmp).as_posix())
            shutil.move(str(rebuilt), str(path))
        print(f"  {path.name}: {widened} of {seen} table(s) widened to the text width")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: fit-docx-tables.py <file.docx> [...]")
    for a in sys.argv[1:]:
        process(Path(a))
