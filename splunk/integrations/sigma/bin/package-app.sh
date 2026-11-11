#!/usr/bin/env bash
# Build a deployable Splunk app package from app/sigma_detection_lab.
#
# Produces sigma_detection_lab-<version>.spl, which is a gzipped tar of the
# app directory, the format Splunk Web's app installer and `splunk install
# app` both accept.
#
#   ./bin/package-app.sh                      # app as it stands
#   ./bin/package-app.sh --rules "./rules-core/SigmaHQ_sigma/core/rules/windows/process_creation \
#                                 ./rules-core/SigmaHQ_sigma/core/rules/linux"
#
# With --rules the detection engine is built into the package, so the app
# arrives ready to detect. Several rule directories can be given in one
# quoted argument. Without --rules the package ships the dashboards and the
# index definition only.
#
# The package carries no local/ directory. Anything written there on an
# instance is operator configuration and must survive a reinstall, so it is
# never shipped.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
APP_SRC="$HERE/app/sigma_detection_lab"
APP_NAME="sigma_detection_lab"
RULES=""
PIPELINE="auto"
OUT_DIR="$HERE/dist"
CONFIG="$HERE/config.yaml"

while [ $# -gt 0 ]; do
    case "$1" in
        --rules)    RULES="${2:-}"; shift 2 ;;
        --pipeline) PIPELINE="${2:-}"; shift 2 ;;
        --out)      OUT_DIR="${2:-}"; shift 2 ;;
        --config)   CONFIG="${2:-}"; shift 2 ;;
        -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

[ -d "$APP_SRC" ] || { echo "FAIL: no app at $APP_SRC" >&2; exit 1; }

VERSION="$(sed -nE 's/^version[[:space:]]*=[[:space:]]*//p' "$APP_SRC/default/app.conf" | head -1)"
VERSION="${VERSION:-0.0.0}"

WORK="$(mktemp -d)"
trap 'rm -rf -- "$WORK"' EXIT
STAGE="$WORK/$APP_NAME"
mkdir -p "$STAGE"

echo "== Stage the app"
# Copy only what belongs in a package. local/ is operator configuration and
# must not be overwritten by an install.
tar -C "$APP_SRC" --exclude='local' --exclude='local.meta' --exclude='*.pyc' \
    --exclude='__pycache__' -cf - . | tar -C "$STAGE" -xf -
printf '  %s files\n' "$(find "$STAGE" -type f | wc -l)"

if [ -n "$RULES" ]; then
    for d in $RULES; do
        [ -d "$d" ] || { echo "FAIL: --rules is not a directory: $d" >&2; exit 1; }
    done
    echo "== Build the detection engine into the package"
    # One search per rule does not survive the scheduler's concurrency cap,
    # so rules are batched by platform and severity and their metadata is
    # written to a lookup the searches and dashboards both read.
    if ! PYTHONPATH="$HERE/pylib:${PYTHONPATH:-}" python3 "$HERE/bin/build-engine.py" \
            $RULES --config "$CONFIG" --pipeline "$PIPELINE" \
            --out-conf "$STAGE/default/savedsearches.conf" \
            --out-lookup "$STAGE/lookups/sigma_rules.csv" \
            --mitre "$STAGE/lookups/mitre_techniques.csv" 2>&1 | sed -n '2,8p' | sed 's/^/  /'; then
        echo "FAIL: engine build failed" >&2; exit 1
    fi
    n=$(grep -c '^\[' "$STAGE/default/savedsearches.conf" || true)
    printf '  %s batched search(es)\n' "${n:-0}"

    # Splunk reads savedsearches.conf and nothing else, so the engine
    # searches that ship with the app are appended rather than left in a
    # file of their own.
    if [ -f "$STAGE/default/savedsearches_engine.conf" ]; then
        printf '\n' >> "$STAGE/default/savedsearches.conf"
        cat "$STAGE/default/savedsearches_engine.conf" >> "$STAGE/default/savedsearches.conf"
        rm -f "$STAGE/default/savedsearches_engine.conf"
        e=$(grep -c '^\[Sigma - ' "$STAGE/default/savedsearches.conf" || true)
        printf '  engine searches merged, %s stanza(s) total\n' \
            "$(grep -c '^\[' "$STAGE/default/savedsearches.conf")"
    fi

    # A malformed stanza is worth catching here rather than on the instance.
    if [ -f "$HERE/planning/savedsearches.conf.spec" ]; then
        echo "== Validate the generated conf"
        python3 "$HERE/bin/validate-savedsearches.py" \
            "$STAGE/default/savedsearches.conf" \
            "$HERE/planning/savedsearches.conf.spec" | sed -n '4,6p' | sed 's/^/  /'
    fi
fi

echo "== Check the package"
# Every conf must parse, or the app fails to load on the instance.
python3 - "$STAGE" <<'PY'
import pathlib, sys
bad = 0
for f in sorted(pathlib.Path(sys.argv[1]).rglob("*.conf")):
    cur = None
    for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = s
            continue
        if "=" not in s:
            print(f"  BAD {f.name}:{n}: not key = value"); bad += 1
        elif cur is None:
            print(f"  BAD {f.name}:{n}: key outside a stanza"); bad += 1
print(f"  {'conf files parse' if not bad else str(bad) + ' problem(s)'}")
sys.exit(1 if bad else 0)
PY
python3 - "$STAGE" <<'PY'
import pathlib, sys, xml.etree.ElementTree as ET
bad = 0
for f in sorted(pathlib.Path(sys.argv[1]).rglob("*.xml")):
    try:
        ET.parse(f)
    except ET.ParseError as e:
        print(f"  BAD {f.name}: {e}"); bad += 1
print(f"  {'views parse' if not bad else str(bad) + ' broken view(s)'}")
sys.exit(1 if bad else 0)
PY

mkdir -p "$OUT_DIR"
PKG="$OUT_DIR/${APP_NAME}-${VERSION}.spl"
echo "== Build $(basename "$PKG")"
# Splunk expects the app directory at the root of the archive.
tar -C "$WORK" -czf "$PKG" "$APP_NAME"
sha256sum "$PKG" | awk '{print $1"  "$2}' > "$PKG.sha256"

printf '  %s  %s bytes\n' "$(basename "$PKG")" "$(stat -c%s "$PKG")"
printf '  sha256 %s\n' "$(cut -d' ' -f1 < "$PKG.sha256")"
echo
echo "Install it with either of:"
echo "  Splunk Web: Apps > Manage Apps > Install app from file"
echo "  CLI:        splunk install app $PKG -auth <user>:<password>"
echo
echo "The app defines its own index, so no index has to be created first."
echo "Restart splunkd after installing."
