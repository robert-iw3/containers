#!/usr/bin/env bash
# Render the topology SVGs to PNG at 2x for slides and documents.
#
#   ./render-png.sh [scale]
#
# librsvg through GObject Introspection, which is already on the host - no
# container, no headless browser, and it honors the SVG's own units so the
# output matches what the file says rather than what a browser decides.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCALE="${1:-2}"

for svg in "$HERE"/*.svg; do
    png="${svg%.svg}.png"
    python3 - "$svg" "$png" "$SCALE" <<'PYIN'
import sys
import cairo
import gi
gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg

src, dst, scale = sys.argv[1], sys.argv[2], float(sys.argv[3])
handle = Rsvg.Handle.new_from_file(src)
ok, w, h = handle.get_intrinsic_size_in_pixels()
if not ok:
    # No intrinsic size means the SVG has only a viewBox. Fall back to it
    # rather than rendering a 0x0 image that reads as a successful run.
    ok, _, vb = handle.get_intrinsic_dimensions()
    w, h = vb.width, vb.height
W, H = int(w * scale), int(h * scale)
surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
ctx = cairo.Context(surface)
ctx.scale(scale, scale)
rect = Rsvg.Rectangle()
rect.x, rect.y, rect.width, rect.height = 0, 0, w, h
handle.render_document(ctx, rect)
surface.write_to_png(dst)
print(f"{dst}  {W}x{H}")
PYIN
done
