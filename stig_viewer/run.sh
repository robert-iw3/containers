#!/usr/bin/env bash
# Launch DISA STIG Viewer 3 in a container, with checklists persisted on the host.
#
# PERSISTENCE IS THE POINT. A checklist is worked over days: opened, statuses set,
# comments written, saved, reopened. SV_CHECKLISTS and SV_STATE are host
# directories mounted read-write, so everything the viewer saves outlives the
# container. The viewer binary and the benchmark library are mounted read-only,
# because nothing the viewer does should alter them.
#
# THE CONTAINER IS THE SANDBOX. Electron's own sandbox needs a setuid-root helper,
# which a rootless container cannot provide, so it runs with --no-sandbox and the
# container boundary takes its place. Capabilities are dropped and privilege
# escalation is blocked, so that boundary is worth something.
#
#   ./run.sh                       open the viewer
#   ./run.sh path/to/file.ckl      open the viewer with a checklist loaded
#   ./run.sh --shell               a shell in the runtime, for diagnosis
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "${HERE}/lib.sh"; sv_load_config

SHELL_MODE=0; OPEN_FILES=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --shell)   SHELL_MODE=1; shift ;;
        -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)         OPEN_FILES+=("$1"); shift ;;
    esac
done

RT="$(sv_runtime)" || exit 3

# ---------------------------------------------------- the viewer binary
VIEWDIR="$(find "$SV_VENDOR" -maxdepth 2 -type d -name 'stig_viewer_3*' 2>/dev/null | sed -n 1p)"
if [ -z "$VIEWDIR" ]; then
    [ -r "$SV_ARCHIVE" ] || {
        printf 'no extracted viewer under %s and no archive at %s\n' "$SV_VENDOR" "$SV_ARCHIVE" >&2
        printf 'set SV_ARCHIVE in stig-viewer.conf to the DISA STIG Viewer zip.\n' >&2
        exit 3; }
    printf 'extracting the viewer once from %s\n' "$(basename "$SV_ARCHIVE")"
    mkdir -p "$SV_VENDOR" && unzip -q "$SV_ARCHIVE" -d "$SV_VENDOR" || exit 3
    VIEWDIR="$(find "$SV_VENDOR" -maxdepth 2 -type d -name 'stig_viewer_3*' | sed -n 1p)"
fi
BIN="$(find "$VIEWDIR" -maxdepth 1 -type f -name 'STIG Viewer*' | sed -n 1p)"
[ -n "$BIN" ] || { printf 'no viewer binary under %s\n' "$VIEWDIR" >&2; exit 3; }
chmod +x "$BIN" 2>/dev/null

# ---------------------------------------------------- the image
if [ -z "$("$RT" images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -Fx "$SV_IMAGE")" ]; then
    printf 'building %s (bounded: 2 CPUs, 2 GB)\n' "$SV_IMAGE"
    "$RT" build --cpu-quota 200000 --memory 2g -t "$SV_IMAGE" -f "${HERE}/Dockerfile" "$HERE" || exit 3
fi

mkdir -p "$SV_CHECKLISTS" "$SV_STATE" "$SV_LIBRARY"

# ---------------------------------------------------- the display
mapfile -t DISP < <(sv_display_args) || true
if [ "${#DISP[@]}" -eq 0 ]; then
    printf 'no Wayland or X11 socket to attach to.\n' >&2
    printf '  WAYLAND_DISPLAY=%s  DISPLAY=%s\n' "${WAYLAND_DISPLAY:-unset}" "${DISPLAY:-unset}" >&2
    exit 3
fi
printf 'display: %s backend\n' "${SV_DISPLAY:-x11}"

# Files named on the command line are copied into the persisted checklist
# directory, so editing them in the viewer edits the host copy and not a
# throwaway inside the container.
ARGS_IN=()
for f in "${OPEN_FILES[@]:-}"; do
    [ -n "$f" ] || continue
    [ -r "$f" ] || { printf 'cannot read %s\n' "$f" >&2; continue; }
    base="$(basename "$f")"
    [ "$(cd "$(dirname "$f")" && pwd)" = "$SV_CHECKLISTS" ] || cp -f "$f" "${SV_CHECKLISTS}/${base}"
    ARGS_IN+=("/checklists/${base}")
done

# Chromium needs more shared memory than a container's 64 MB default; starved, it
# renders a blank window rather than failing outright.
# --userns=keep-id maps the invoking user to the same uid inside, so the mounted
# host directories are writable by the process. Without it a rootless runtime maps
# the host user to container root, the unprivileged account in the image cannot
# write to its own config directory, and Electron dies with
# "Failed to get 'userData' path" before a window ever appears.
LIMITS=(--cpus "$SV_CPUS" --memory "$SV_MEMORY" --pids-limit "$SV_PIDS" --shm-size 512m
        --cap-drop ALL --cap-add SETFCAP --cap-add SYS_CHROOT
        --security-opt no-new-privileges)
[ "$RT" = podman ] && LIMITS+=(--userns=keep-id)
# A system bus is absent and Electron reports it; harmless, and silenced so a real
# error is not lost in it.
LIMITS+=(--env=NO_AT_BRIDGE=1 --env=DBUS_SESSION_BUS_ADDRESS=disabled:)
MOUNTS=(-v "${VIEWDIR}":/opt/sv:ro,Z
        -v "${SV_LIBRARY}":/library:ro,Z
        -v "${SV_CHECKLISTS}":/checklists:rw,Z
        -v "${SV_STATE}":/state:rw,Z
        --env=XDG_CONFIG_HOME=/state
        --env=XDG_CACHE_HOME=/state/cache
        --env=HOME=/state)

if [ "$SHELL_MODE" -eq 1 ]; then
    exec "$RT" run --rm -it "${LIMITS[@]}" "${MOUNTS[@]}" "${DISP[@]}" "$SV_IMAGE"
fi

printf 'checklists: %s (read-write, persisted)\n' "${SV_CHECKLISTS#"$HERE"/}"
printf 'library   : %s (read-only)\n' "${SV_LIBRARY#"$HERE"/}"
[ "${#ARGS_IN[@]}" -gt 0 ] && printf 'opening   : %s\n' "${ARGS_IN[*]}"

exec "$RT" run --rm --name stig-viewer "${LIMITS[@]}" "${MOUNTS[@]}" "${DISP[@]}" \
    "$SV_IMAGE" -c '
        # NEVER START A WINDOW MANAGER HERE.
        #
        # The X11 socket mounted into this container is the HOST\x27s display. On a
        # Wayland session the compositor already manages XWayland clients, so a
        # window manager started in here is a second one competing for the host
        # session - and `openbox --replace` takes the session over and crashes it.
        # That happened on 2026-11-10. The window is managed by the desktop the
        # socket belongs to; this container only draws into it.
        exec "/opt/sv/STIG Viewer 3" --no-sandbox --disable-dev-shm-usage \
            --ozone-platform="${SV_OZONE:-x11}" ${SV_EXTRA_FLAGS:-} "$@"' \
    _ "${ARGS_IN[@]:-}"
