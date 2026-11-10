# Shared helpers: configuration, container runtime detection, display selection.

sv_load_config() {
    HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
    # shellcheck disable=SC1091
    [ -r "${HERE}/stig-viewer.conf" ] && . "${HERE}/stig-viewer.conf"
    # An environment variable of the same name wins, so the config file states
    # defaults rather than dictating them.
    for v in SV_ARCHIVE SV_VENDOR SV_LIBRARY SV_BENCHMARKS SV_CHECKLISTS SV_STATE \
             SV_CPUS SV_MEMORY SV_PIDS SV_IMAGE; do
        eval "cur=\${$v:-}"
        [ -n "${cur:-}" ] || continue
    done
    # Resolve the relative paths against this directory, not the caller's cwd.
    for v in SV_VENDOR SV_LIBRARY SV_CHECKLISTS SV_STATE; do
        eval "p=\$$v"
        case "$p" in /*) : ;; *) eval "$v=\"\${HERE}/\${p#./}\"" ;; esac
    done
    SV_ARCHIVE="${SV_ARCHIVE/#\~/$HOME}"
}

sv_runtime() {
    for c in podman docker; do
        command -v "$c" >/dev/null 2>&1 && { printf '%s' "$c"; return 0; }
    done
    printf 'neither podman nor docker is on PATH\n' >&2
    return 3
}

# Wayland first where the compositor offers it: unlike X11, a Wayland client
# cannot read other clients' windows or keystrokes. X11 is the fallback, and on a
# Wayland session that means XWayland, which is why DISPLAY is still set.
sv_display_args() {
    case "${SV_DISPLAY:-x11}" in
      wayland|auto)
        if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -S "${XDG_RUNTIME_DIR:-/nonexistent}/${WAYLAND_DISPLAY}" ]; then
            printf '%s\n' "--env=WAYLAND_DISPLAY=${WAYLAND_DISPLAY}" \
                "--env=XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR}" \
                "--volume=${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}:${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}:rw" \
                "--env=SV_OZONE=wayland"
            return 0
        fi
        [ "${SV_DISPLAY:-}" = wayland ] && {
            printf 'SV_DISPLAY=wayland but no compositor socket at %s/%s\n' \
                "${XDG_RUNTIME_DIR:-unset}" "${WAYLAND_DISPLAY:-unset}" >&2
            return 1; }
        ;;
    esac
    # X11, including XWayland on a Wayland session.
    if [ -n "${DISPLAY:-}" ] && [ -S "/tmp/.X11-unix/X${DISPLAY#*:}" ]; then
        printf '%s\n' "--env=DISPLAY=${DISPLAY}" \
            "--volume=/tmp/.X11-unix:/tmp/.X11-unix:rw" \
            "--env=SV_OZONE=x11"
        # The X server authorizes by cookie, not by uid, so a client with the
        # socket and no cookie is refused - and the refusal is reported as
        # "Missing X server or $DISPLAY", which sends you looking for the wrong
        # fault entirely. The authority FILE is mounted read-only; its contents
        # are never read by this tool.
        xa="${XAUTHORITY:-$HOME/.Xauthority}"
        if [ -f "$xa" ]; then
            printf '%s\n' "--volume=${xa}:/state/.Xauthority:ro" \
                "--env=XAUTHORITY=/state/.Xauthority"
        else
            printf 'no X authority file at %s; the server will refuse the client\n' "$xa" >&2
            printf '  set XAUTHORITY, or use SV_DISPLAY=wayland\n' >&2
        fi
        return 0
    fi
    printf 'no usable display: DISPLAY=%s, WAYLAND_DISPLAY=%s\n' \
        "${DISPLAY:-unset}" "${WAYLAND_DISPLAY:-unset}" >&2
    return 1
}
