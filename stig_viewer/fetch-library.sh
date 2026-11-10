#!/usr/bin/env bash
# Build and catalog a benchmark library from DISA archives.
#
# GENERAL PURPOSE. It ingests any DISA distribution: a single SRG or STIG zip, or
# the full quarterly compilation, which is zips inside a zip. It finds every XCCDF
# document however deeply nested, copies it into the library, and catalogs what it
# found by reading the document rather than by parsing a file name.
#
#   fetch-library.sh --zip PATH        ingest a local archive (the air-gapped path)
#   fetch-library.sh --url URL         download an archive, then ingest it
#   fetch-library.sh --list            show the catalog
#   fetch-library.sh --rebuild-index   re-read the library and rewrite the catalog
#
# A URL IS NEVER ASSUMED. The compilation's name changes every quarter, so this
# does not guess one. Obtain the link from the DISA STIG downloads page and pass
# it, or download it elsewhere and pass the file. --url prints what it is about to
# fetch and its size before it starts.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "${HERE}/lib.sh"; sv_load_config

MODE=""; ARG=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --zip)           MODE=zip;     ARG="${2:-}"; shift 2 ;;
        --url)           MODE=url;     ARG="${2:-}"; shift 2 ;;
        --list)          MODE=list;    shift ;;
        --rebuild-index) MODE=index;   shift ;;
        -h|--help)       sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'unknown argument: %s\n' "$1" >&2; exit 3 ;;
    esac
done
[ -n "$MODE" ] || { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 3; }

mkdir -p "$SV_LIBRARY" || exit 3
INDEX="${SV_LIBRARY}/catalog.tsv"

# Read identity out of the document. A file name is a convention; the document is
# the fact, and a compilation mixes naming conventions across years.
catalog_one() {
    python3 -I - "$1" <<'PY'
import sys, re, xml.etree.ElementTree as ET
p = sys.argv[1]
try:
    root = ET.parse(p).getroot()
except Exception as e:
    print('\t'.join(['?', '?', '?', '0', 'unparseable: %s' % e]))
    sys.exit(0)
ns = {'x': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
def t(tag):
    e = root.find('x:%s' % tag, ns) if ns else root.find(tag)
    return ' '.join((e.text or '').split()) if e is not None else ''
rules = [r for r in root.iter() if r.tag.split('}')[-1] == 'Rule']
bid = root.get('id') or ''
# Release info lives in plain-text metadata, so it is matched rather than parsed.
blob = ET.tostring(root, encoding='unicode')[:40000]
m = re.search(r'Release:\s*(\d+)\s*Benchmark Date:\s*([0-9]{1,2} \w+ [0-9]{4})', blob)
rel = ('Release: %s Benchmark Date: %s' % (m.group(1), m.group(2))) if m else ''
ver = t('version')
print('\t'.join([bid or '?', t('title') or '?', ver or '?', str(len(rules)), rel]))
PY
}

rebuild_index() {
    printf 'file\tbenchmark_id\ttitle\tversion\trules\trelease\n' > "$INDEX"
    n=0
    for f in "$SV_LIBRARY"/*.xml; do
        [ -f "$f" ] || continue
        meta="$(catalog_one "$f")"
        printf '%s\t%s\n' "$(basename "$f")" "$meta" >> "$INDEX"
        n=$((n+1))
    done
    printf 'cataloged %s benchmark(s) -> %s\n' "$n" "${INDEX#"$HERE"/}"
}

# DISA archives nest: the compilation holds per-technology zips, each holding the
# XCCDF plus PDFs and a stylesheet. Recurse until no zip is left.
ingest() {
    local src="$1" depth="${2:-0}" tmp
    [ "$depth" -gt 4 ] && return 0
    tmp="$(mktemp -d)" || return 3
    if ! unzip -qq -o "$src" -d "$tmp" 2>/dev/null; then
        printf '  cannot read as a zip: %s\n' "$(basename "$src")" >&2
        rm -rf "$tmp"; return 1
    fi
    # XCCDF documents first.
    find "$tmp" -type f -name '*xccdf*.xml' 2>/dev/null | while read -r x; do
        cp -f "$x" "${SV_LIBRARY}/$(basename "$x")" && printf '  + %s\n' "$(basename "$x")"
    done
    # Then any nested archive.
    find "$tmp" -type f -name '*.zip' 2>/dev/null | while read -r z; do
        ingest "$z" "$((depth+1))"
    done
    # DISA archives carry read-only modes, so the extraction is not removable
    # until it is made writable. And cleanup must not decide the function's exit
    # status: an unremovable temporary directory is untidy, not a failed ingest,
    # and letting it propagate skipped the catalog rebuild entirely.
    chmod -R u+w "$tmp" 2>/dev/null || true
    rm -rf "$tmp" 2>/dev/null || true
    return 0
}

case "$MODE" in
  list|index)
      [ "$MODE" = index ] && rebuild_index
      if [ ! -s "$INDEX" ]; then printf 'library is empty: %s\n' "$SV_LIBRARY"; exit 0; fi
      printf '\n%-52s %-9s %7s  %s\n' "TITLE" "VERSION" "RULES" "RELEASE"
      awk -F'\t' 'NR>1 {printf "%-52s %-9s %7s  %s\n", substr($3,1,52), $4, $5, $6}' "$INDEX" | sort
      printf '\n%s benchmark(s) in %s\n' "$(($(wc -l < "$INDEX")-1))" "${SV_LIBRARY#"$HERE"/}"
      ;;
  zip)
      [ -r "$ARG" ] || { printf 'cannot read %s\n' "$ARG" >&2; exit 3; }
      printf 'ingesting %s (%s)\n' "$(basename "$ARG")" "$(du -h "$ARG" | awk '{print $1}')"
      ingest "$ARG" && rebuild_index
      ;;
  url)
      [ -n "$ARG" ] || { printf '--url needs a URL\n' >&2; exit 3; }
      command -v curl >/dev/null 2>&1 || { printf 'curl is not available\n' >&2; exit 3; }
      sz="$(curl -sIL "$ARG" 2>/dev/null | awk 'BEGIN{IGNORECASE=1}/^content-length:/{v=$2}END{print v+0}')"
      printf 'about to download:\n  %s\n  %s bytes\n' "$ARG" "${sz:-unknown}"
      dl="$(mktemp -d)/archive.zip"
      if curl -fL --retry 2 -o "$dl" "$ARG"; then
          printf 'sha256 %s\n' "$(sha256sum "$dl" | awk '{print $1}')"
          ingest "$dl" && rebuild_index
      else
          printf 'download failed\n' >&2; exit 1
      fi
      rm -rf "$(dirname "$dl")"
      ;;
esac
