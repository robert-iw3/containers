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
# A WINDOW PARSES ITS CHECKLIST ONCE. The viewer reads the file when it opens it
# and keeps that parse for the life of the window: it does not watch the file and
# offers no reload. Regenerate a checklist while the viewer is open and the file
# changes while the window does not, which is an assessor reading numbers that
# are hours old. There is no way to refresh a window in place, so this script
# refuses to stage a checklist behind a running viewer. It reports when that
# viewer started and what it opened, and --replace stops it so the relaunch
# parses the new file.
#
# WHAT IS OPENED IS A COPY. A file named on the command line is copied into the
# persisted checklist directory and the viewer opens the copy, so saves and
# autosaves land there, not on the file that was named. Each run prints the size,
# modification time and SHA-256 of the copy it staged, which is what the window
# then shows. A copy that has changed since it was staged is left alone unless
# --restage says otherwise, because that change is most likely the viewer saving
# an assessor's work.
#
#   ./run.sh                       open the viewer
#   ./run.sh path/to/file.ckl      open the viewer with a checklist loaded
#   ./run.sh --replace file.cklb   stop a viewer that is already running, so the
#                                  file is parsed again
#   ./run.sh --restage file.cklb   overwrite a staged copy that has diverged
#   ./run.sh --shell               a shell in the runtime, for diagnosis
#
# Exit codes: 3 the setup is incomplete, 4 a viewer is already running,
# 5 a staged copy has diverged from the file named.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "${HERE}/lib.sh"; sv_load_config
# One window at a time, by name, so a second launch is detected rather than
# colliding inside the container runtime.
SV_NAME="${SV_NAME:-stig-viewer}"

SHELL_MODE=0; REPLACE=0; RESTAGE=0; OPEN_FILES=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --shell)   SHELL_MODE=1; shift ;;
        --replace) REPLACE=1; shift ;;
        --restage) RESTAGE=1; shift ;;
        # The help text is the comment block at the top of this file, so the two
        # cannot drift apart.
        -h|--help) awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"; exit 0 ;;
        *)         OPEN_FILES+=("$1"); shift ;;
    esac
done

RT="$(sv_runtime)" || exit 3

# Size, modification time and digest of one file, so the run states what the
# window will show rather than asking anyone to trust that a copy happened.
sv_fingerprint() {
    local p="$1" sum
    sum="$(sha256sum "$p" 2>/dev/null | cut -c1-12)"
    printf '%s bytes, %s, sha256 %s' \
        "$(stat -c %s "$p" 2>/dev/null)" \
        "$(stat -c %y "$p" 2>/dev/null | cut -d. -f1)" \
        "${sum:-unavailable}"
}

sv_container_state() { "$RT" inspect "$SV_NAME" --format '{{.State.Status}}' 2>/dev/null; }

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

printf 'checklists: %s (read-write, persisted)\n' "${SV_CHECKLISTS#"$HERE"/}"
printf 'library   : %s (read-only)\n' "${SV_LIBRARY#"$HERE"/}"

# ---------------------------------------------------- the checklist copies
# Every copy is checked before any of them is written, and before a running
# viewer is touched, so a refusal leaves both the files and the open window as
# they were rather than part of the run applied.
SRCS=(); DSTS=(); REFUSED=0
for f in "${OPEN_FILES[@]:-}"; do
    [ -n "$f" ] || continue
    [ -r "$f" ] || { printf 'cannot read %s\n' "$f" >&2; continue; }
    base="$(basename "$f")"
    dst="${SV_CHECKLISTS}/${base}"
    if [ "$(cd "$(dirname "$f")" && pwd)" = "$SV_CHECKLISTS" ]; then
        # Named in place: it is already the persisted copy, so nothing is copied.
        SRCS+=(""); DSTS+=("$dst"); continue
    fi
    # cp -p below carries the source timestamp onto the copy, so a copy newer
    # than its source means something wrote to the copy - the viewer saving, most
    # likely - and overwriting it would discard that.
    if [ -e "$dst" ] && ! cmp -s "$f" "$dst" && [ "$dst" -nt "$f" ] && [ "$RESTAGE" -eq 0 ]; then
        printf 'the staged copy of %s differs from the file you named and is newer than it.\n' "$base" >&2
        printf '  staged: %s\n          %s\n' "${dst#"$HERE"/}" "$(sv_fingerprint "$dst")" >&2
        printf '  named : %s\n          %s\n' "$f" "$(sv_fingerprint "$f")" >&2
        printf 'that is what the viewer having saved into it looks like. Copy the staged file\n' >&2
        printf 'somewhere safe, or re-run with --restage to overwrite it.\n' >&2
        REFUSED=1; continue
    fi
    SRCS+=("$f"); DSTS+=("$dst")
done
[ "$REFUSED" -eq 0 ] || exit 5

# ---------------------------------------------------- a viewer already running
# Settled before anything is staged. A running window will not re-read its
# checklist and a second container cannot take the name, so staging first would
# leave the file on disk correct, the window stale, and the run dead on a name
# collision - which is exactly the state this check exists to prevent.
STATE="$(sv_container_state)"
if [ "$SHELL_MODE" -eq 0 ] && [ -n "$STATE" ]; then
    if [ "$STATE" != running ]; then
        printf 'removing  : a %s container named %s, left over from an earlier run\n' \
            "$STATE" "$SV_NAME"
        "$RT" rm -f "$SV_NAME" >/dev/null 2>&1 || {
            printf 'could not remove the container named %s\n' "$SV_NAME" >&2; exit 3; }
    else
        STARTED="$("$RT" inspect "$SV_NAME" --format '{{.State.StartedAt}}' 2>/dev/null | cut -c1-19)"
        # The launch arguments record which checklists that window was told to
        # open, which is the only account of it available from outside.
        HELD="$("$RT" inspect "$SV_NAME" --format '{{range .Config.Cmd}}{{println .}}{{end}}' \
            2>/dev/null | sed -n 's#^/checklists/#              #p')"
        printf 'viewer    : already running, started %s\n' "${STARTED:-at an unknown time}"
        [ -n "$HELD" ] && printf 'it opened :\n%s\n' "$HELD"
        printf 'that window parsed its checklist when it opened it and will not read the file\n'
        printf 'again, so a regenerated checklist cannot reach it.\n'
        if [ "$REPLACE" -eq 0 ] && [ "${#OPEN_FILES[@]}" -eq 0 ]; then
            printf 'no checklist named, so nothing is stale; leaving that window alone.\n'
            exit 0
        fi
        if [ "$REPLACE" -eq 0 ] && [ -t 0 ]; then
            printf 'stop it and relaunch? anything it has not saved is lost [y/N] '
            read -r ANSWER || ANSWER=""
            case "${ANSWER:-}" in y|Y|yes|YES) REPLACE=1 ;; esac
        fi
        if [ "$REPLACE" -eq 0 ]; then
            printf 'left running and nothing staged, so what you are looking at is unchanged.\n' >&2
            printf 'close that window, or re-run with --replace to stop it from here.\n' >&2
            exit 4
        fi
        printf 'stopping  : %s\n' "$SV_NAME"
        "$RT" stop -t 10 "$SV_NAME" >/dev/null 2>&1
        # --rm removes it on exit, so wait for the name rather than assuming.
        WAITED=0
        while [ "$WAITED" -lt 30 ] && [ -n "$(sv_container_state)" ]; do
            sleep 1; WAITED=$((WAITED + 1))
        done
        [ -n "$(sv_container_state)" ] && "$RT" rm -f "$SV_NAME" >/dev/null 2>&1
        [ -n "$(sv_container_state)" ] && {
            printf 'the container named %s is still there; stop it by hand\n' "$SV_NAME" >&2
            exit 3; }
    fi
fi

ARGS_IN=()
for i in "${!DSTS[@]}"; do
    [ -z "${SRCS[$i]}" ] || cp -p -f "${SRCS[$i]}" "${DSTS[$i]}" || exit 3
    printf 'staged    : %s\n            %s\n' \
        "$(basename "${DSTS[$i]}")" "$(sv_fingerprint "${DSTS[$i]}")"
    ARGS_IN+=("/checklists/$(basename "${DSTS[$i]}")")
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

if [ "${#ARGS_IN[@]}" -gt 0 ]; then
    printf 'opening   : %s\n' "${ARGS_IN[*]}"
    printf 'note      : this window parses those files once. Regenerate one and it keeps\n'
    printf '            showing what it parsed; re-run with --replace to see the new one.\n'
fi

exec "$RT" run --rm --name "$SV_NAME" "${LIMITS[@]}" "${MOUNTS[@]}" "${DISP[@]}" \
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
