#!/usr/bin/env bash
# Run this tool's scripts inside a container, then bring the results back out.
#
# WHY THIS EXISTS. The scripts have ONE code path: they run on the instance they
# assess, as the account that owns it. Assessing a containerized Splunk therefore
# is not a second code path through `exec` - it is the same scripts, copied in and
# run there. Two code paths means the one under test is not the one that runs in
# production, and a container run then proves nothing about a host install.
#
# It also means a container run exercises discovery, the privilege guard, btool,
# the log reads and df exactly as they will behave on bare metal.
#
#   in-container.sh CONTAINER SCRIPT [ARGS...]
#
#   in-container.sh epo-uat-indexer health-check.sh --baseline
#   in-container.sh epo-uat-uf     assess.sh
#
# The container runtime is detected: podman, else docker. Results are copied to
# out/<container>/ on this host. The script's exit code is propagated unchanged -
# a wrapper that loses it turns a failed assessment into a silent success.
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
CT="${1:-}"; SCRIPT="${2:-}"
[ -n "$CT" ] && [ -n "$SCRIPT" ] || { sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 3; }
shift 2

if [ -t 1 ]; then G=$'\033[32m'; R=$'\033[31m'; B=$'\033[1m'; Z=$'\033[0m'
else G=""; R=""; B=""; Z=""; fi

# ------------------------------------------------------- 1. which runtime is it
RT=""
for c in podman docker; do
    if command -v "$c" >/dev/null 2>&1; then
        if [ -n "$("$c" ps --format '{{.Names}}' 2>/dev/null | grep -Fx "$CT")" ]; then
            RT="$c"; break
        fi
    fi
done
if [ -z "$RT" ]; then
    printf '%sno running container named %s under podman or docker%s\n' "$R" "$CT" "$Z" >&2
    for c in podman docker; do
        command -v "$c" >/dev/null 2>&1 && printf '  %s sees: %s\n' "$c" \
            "$("$c" ps --format '{{.Names}}' 2>/dev/null | paste -sd' ' -)" >&2
    done
    exit 3
fi
printf '%s== %s in %s (%s)%s\n' "$B" "$SCRIPT" "$CT" "$RT" "$Z"

# -------------------------------------------- 2. who owns the installation there
# The scripts refuse to run as the wrong account, so the right one is found here
# rather than assumed: an image may run Splunk as splunk, as root, or as a uid
# with no name.
HOME_IN=""
for c in /opt/splunk /opt/splunkforwarder /usr/local/splunk; do
    if [ -n "$("$RT" exec "$CT" sh -c "[ -x '${c}/bin/splunk' ] && echo y" 2>/dev/null)" ]; then
        HOME_IN="$c"; break
    fi
done
[ -n "$HOME_IN" ] || { printf '%sno Splunk installation inside %s%s\n' "$R" "$CT" "$Z" >&2; exit 3; }
OWNER="$("$RT" exec "$CT" sh -c "ls -ld '${HOME_IN}/etc' 2>/dev/null | awk '{print \$3}'" 2>/dev/null)"
[ -n "$OWNER" ] || OWNER="root"
printf '   SPLUNK_HOME %s, owned by %s\n' "$HOME_IN" "$OWNER"

# ------------------------------------------------------------- 3. copy the tool in
DEST="/tmp/splunk-harden-$$"
"$RT" exec -u 0 "$CT" sh -c "rm -rf '$DEST'; mkdir -p '$DEST/bin' '$DEST/inventory' '$DEST/out' '$DEST/lib'" 2>/dev/null \
    || { printf '%scannot create %s inside the container%s\n' "$R" "$DEST" "$Z" >&2; exit 3; }

copied=0
for f in "${HERE}"/bin/*.sh; do
    case "$(basename "$f")" in
        in-container.sh) continue ;;   # the wrapper does not belong inside
    esac
    "$RT" cp "$f" "${CT}:${DEST}/bin/" 2>/dev/null && copied=$((copied+1))
done
for f in "${HERE}"/inventory/checks.tsv "${HERE}"/inventory/rules.tsv; do
    [ -f "$f" ] && "$RT" cp "$f" "${CT}:${DEST}/inventory/" 2>/dev/null
done
# The shared library travels too: the scripts source it and cannot run without it.
for f in "${HERE}"/../lib/*.sh; do
    [ -f "$f" ] && "$RT" cp "$f" "${CT}:${DEST}/lib/" 2>/dev/null
done
# A prior baseline must travel in, or every run reports "no baseline to compare".
if [ -d "${HERE}/out/${CT}" ]; then
    for f in "${HERE}/out/${CT}"/baseline-*.tsv; do
        [ -f "$f" ] && "$RT" cp "$f" "${CT}:${DEST}/out/" 2>/dev/null
    done
fi
"$RT" exec -u 0 "$CT" sh -c "chmod +x '$DEST'/bin/*.sh 2>/dev/null; chown -R '${OWNER}' '$DEST' 2>/dev/null" 2>/dev/null
printf '   staged      %s script(s) at %s\n\n' "$copied" "$DEST"

# ----------------------------------------------------- 4. run it as that account
# The exit code is the result. It is captured before anything else can clobber it,
# and never passed through a pipe, which would report the pipe's status instead.
set +e
"$RT" exec -u "$OWNER" -w "$DEST" "$CT" "./bin/${SCRIPT}" "$@"
RC=$?
set -e

# ----------------------------------------------------------- 5. bring results out
LOCAL_OUT="${HERE}/out/${CT}"
mkdir -p "$LOCAL_OUT"
if "$RT" cp "${CT}:${DEST}/out/." "$LOCAL_OUT/" 2>/dev/null; then
    n="$(ls -1 "$LOCAL_OUT" 2>/dev/null | wc -l)"
    printf '\n   results     %s (%s file(s))\n' "$LOCAL_OUT" "$n"
else
    printf '\n   %sno results were produced inside the container%s\n' "$R" "$Z" >&2
fi
"$RT" exec -u 0 "$CT" sh -c "rm -rf '$DEST'" 2>/dev/null || true

if [ "$RC" -eq 0 ]; then printf '   %sexit %s%s\n' "$G" "$RC" "$Z"
else printf '   %sexit %s%s\n' "$R" "$RC" "$Z"; fi
exit "$RC"
