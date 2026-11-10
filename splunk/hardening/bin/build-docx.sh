#!/usr/bin/env bash
# Render the hardening documents to Word beside their markdown.
#
# RENDERING HAPPENS IN A CONTAINER, NOT ON THE HOST, so the output does not depend
# on whatever pandoc a workstation happens to carry. localhost/hx-docs:1 is the
# project's documentation renderer; it is defined in trellix/hx/build/Containerfile
# and built with
#   podman compose -f trellix/hx/build/compose.yaml build render
#
# The run is bounded and offline: 2 CPUs, 2 GB, --network none. A render that needs
# to fetch something is a defect, and this makes it fail rather than quietly succeed.
#
# THE READER IS gfm. pandoc's own markdown reader mis-parses a table cell holding a
# backtick-quoted value after an escaped pipe, which collapses every following row
# into one column while exiting 0.
#
# STYLING comes from the governance reference documents in the trellix repository,
# so these read like the other assessment artifacts rather than like pandoc output.
# Tables of four or more columns render landscape; the applicability matrix needs it.
#
# This is the sibling of epo_splunk_app/bin/build-docx.sh and shares its three
# post-processors: bookmarks stripped, wide tables refitted so the renderer stops
# breaking words in half, and the zip entry dates and docProps stamped from
# SOURCE_DATE_EPOCH so the same markdown always gives the same sha256.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${DOCX_IMAGE:-localhost/hx-docs:1}"
LANDSCAPE_MIN_COLUMNS=4

ok()  { printf '  \033[32m[ OK ]\033[0m %s\n' "$1"; }
bad() { printf '  \033[31m[FAIL]\033[0m %s\n' "$1"; [ -n "${2:-}" ] && printf '         %s\n' "$2"; FAILED=1; }
FAILED=0

# The reference documents live in another repository, so this is searched and loud
# rather than a relative path that silently resolves to nothing.
find_ref_dir() {
    if [ -n "${REF_DIR:-}" ]; then (cd "$REF_DIR" && pwd); return; fi
    for c in "${HERE}/../../../trellix/implementation/governance" \
             "${HERE}/../../../../trellix/implementation/governance" \
             "${HOME}/Documents/GitHub/trellix/implementation/governance"; do
        [ -f "${c}/.governance-reference.docx" ] && { (cd "$c" && pwd); return; }
    done
    echo "cannot find the governance reference documents." >&2
    echo "  looked for a directory containing .governance-reference.docx" >&2
    echo "  set REF_DIR to point at it." >&2
    exit 1
}
REF_DIR="$(find_ref_dir)"
for f in "${REF_DIR}/.governance-reference.docx" "${REF_DIR}/.governance-reference-landscape.docx"; do
    [ -f "$f" ] || { echo "missing reference document: $f" >&2; exit 1; }
done

# The widest pipe table, in columns. An escaped pipe is content, not a separator:
# counting it would split one column in two and send a narrow table to landscape.
widest_table() {
    sed 's/\\|/\x01/g' "$1" |
    awk -F'|' '/^\|/ { n = NF - 2; if (n > w) w = n } END { print w + 0 }'
}

render() {
    local md="$1" out ref rel cols orient
    out="${md%.md}.docx"
    rel="${md#"${HERE}"/}"
    if [ "$rel" = "$md" ]; then
        bad "$(basename "$md")" "outside ${HERE}; the renderer only mounts this tree"
        return
    fi
    cols=$(widest_table "$md")
    if [ "$cols" -ge "$LANDSCAPE_MIN_COLUMNS" ]; then
        ref=".governance-reference-landscape.docx"; orient=landscape
    else
        ref=".governance-reference.docx"; orient=portrait
    fi

    if podman run --rm --network none --cpus 2 --memory 2g \
            -v "${HERE}":/work:z -v "${REF_DIR}":/ref:ro,z -w /work \
            --entrypoint sh "$IMAGE" -c "
                set -e
                pandoc '/work/${rel}' -o '/work/${rel%.md}.docx' \
                    --reference-doc='/ref/${ref}' \
                    --from=gfm+pipe_tables+footnotes --to=docx
                python3 /work/bin/strip-docx-bookmarks.py '/work/${rel%.md}.docx'
                python3 /work/bin/fit-docx-tables.py '/work/${rel%.md}.docx' >/dev/null
                python3 /work/bin/normalize-docx.py '/work/${rel%.md}.docx'
            " 2>/tmp/harden-docx.err.$$; then
        ok "$(basename "$out")  (${cols} col table, ${orient}, $(wc -c < "$out") bytes)"
    else
        bad "$(basename "$md")" "$(head -3 /tmp/harden-docx.err.$$ | tr '\n' ' ')"
    fi
    rm -f /tmp/harden-docx.err.$$
}

if [ "$#" -gt 0 ]; then
    for f in "$@"; do render "$(cd "$(dirname "$f")" && pwd)/$(basename "$f")"; done
else
    shopt -s nullglob
    for f in "${HERE}"/*.md; do render "$f"; done
fi

[ "$FAILED" -eq 0 ] || exit 1
