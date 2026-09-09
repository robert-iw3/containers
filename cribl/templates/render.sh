#!/usr/bin/env bash
# Render the Cribl -> Splunk templates into a deployable worker group.
#
#   cp site.env.example site.env    edit it
#   ./render.sh out/                writes a group directory
#   ./validate.sh out/              checks it against Cribl's own schema
#
# Then copy the result to the leader:
#
#   podman cp out/. <leader>:/opt/cribl/groups/<group>/local/cribl/
#
# ...commit and deploy it, and confirm a worker actually opened the listener.
# A Source present in the applied config with no socket behind it is a real and
# distinguishable state, and it is the one that looks like a quiet network.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:?usage: render.sh <out-dir> [--env FILE]}"; shift || true
ENVFILE="${HERE}/site.env"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env) ENVFILE="$2"; shift 2 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

[[ -f "$ENVFILE" ]] || { echo "render.sh: no $ENVFILE - copy site.env.example first" >&2; exit 1; }
set -a; . "$ENVFILE"; set +a

# Refuse the placeholder token rather than rendering a Destination that answers
# 401 to everything while every Cribl-side check still passes.
if [[ "${CRIBL_DEST_TYPE:-hec}" == "hec" ]]; then
    case "${CRIBL_HEC_TOKEN:-}" in
        ""|REPLACE-WITH-A-REAL-TOKEN)
            echo "render.sh: CRIBL_HEC_TOKEN is unset or still the placeholder" >&2
            echo "           an empty token makes Splunk reject every event with 401," >&2
            echo "           and nothing on the Cribl side reports a problem" >&2
            exit 1 ;;
    esac
fi

mkdir -p "$OUT/pipelines"
rm -rf "$OUT/pipelines"/*

# S2S hosts arrive comma separated and have to become a YAML list of objects.
s2s_yaml() {
    local out="" h p
    IFS=',' read -ra items <<< "${CRIBL_S2S_HOSTS:-}"
    for item in "${items[@]}"; do
        h="${item%%:*}"; p="${item##*:}"
        out+=$'\n      - host: '"${h}"$'\n        port: '"${p}"
    done
    printf '%s' "$out"
}

# Every __NAME__ token is replaced by $NAME from site.env. A token with no
# variable behind it is left in place and caught below, rather than rendered as
# an empty string into a filter that then matches everything.
render() { # render <src> <dst>
    local src="$1" dst="$2"
    python3 - "$src" "$dst" <<'PYIN'
import os, re, sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src).read()
def sub(m):
    name = m.group(1)
    val = os.environ.get(name)
    return m.group(0) if val is None else val
open(dst, "w").write(re.sub(r"__([A-Z0-9_]+)__", sub, text))
PYIN
}

CRIBL_S2S_HOSTS_YAML="$(s2s_yaml)"; export CRIBL_S2S_HOSTS_YAML

render "$HERE/group/inputs.yml.tmpl" "$OUT/inputs.yml"
render "$HERE/group/route.yml.tmpl"  "$OUT/route.yml"
case "${CRIBL_DEST_TYPE:-hec}" in
    hec) render "$HERE/group/outputs.yml.hec.tmpl" "$OUT/outputs.yml" ;;
    s2s) render "$HERE/group/outputs.yml.s2s.tmpl" "$OUT/outputs.yml" ;;
    *)   echo "render.sh: CRIBL_DEST_TYPE must be hec or s2s" >&2; exit 2 ;;
esac

count=0
for dir in "$HERE"/group/pipelines/*/; do
    name="$(basename "$dir")"
    mkdir -p "$OUT/pipelines/$name"
    render "$dir/conf.yml" "$OUT/pipelines/$name/conf.yml"
    count=$((count + 1))
done

# A surviving token means a variable is missing from site.env. Rendering it as
# an empty string would produce config that loads and behaves differently from
# what it reads like, which is worse than a failed render.
if grep -rlE "__[A-Z0-9_]+__" "$OUT" >/dev/null 2>&1; then
    echo "render.sh: unresolved tokens - add these to site.env:" >&2
    grep -rhoE "__[A-Z0-9_]+__" "$OUT" | sort -u | sed 's/^/  /' >&2
    exit 1
fi

# The token must not survive into a file anyone might commit.
chmod 600 "$OUT/outputs.yml"

echo "render.sh: ${count} pipelines + inputs.yml, outputs.yml (${CRIBL_DEST_TYPE:-hec}), route.yml -> ${OUT}"
echo "render.sh: next, ./validate.sh ${OUT}"
