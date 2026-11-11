#!/usr/bin/env bash
# Shared transport layer for reaching a Splunk instance, whatever it runs on.
#
# Source this; it defines functions and sets no policy. A substrate is added
# here once rather than in each script.
#
# A target is TRANSPORT:LOCATION.
#
#   local:/opt/splunk                     this machine, bare metal or a VM
#   ssh:splunk@idx01.example.com          a remote host
#   podman:splunk-idx                     a podman container
#   docker:splunk-idx                     a docker container
#   k8s:splunk/splunk-idxc-0              a pod, namespace/pod
#   k8s:splunk/splunk-idxc-0/splunk       a named container in that pod
#
# Not every operation is valid on every substrate, and pretending otherwise
# produces changes that vanish. Ask before acting:
#
#   t_can_persist <target>   does writing to the filesystem survive a restart?
#
# On a container or a pod built from an image, a file written into the running
# instance is lost when it is replaced. That is fine for a probe or a one-off
# test, and wrong for configuration meant to last. For Kubernetes the answer
# is a ConfigMap or an app baked into the image; for a plain container, a
# volume or a rebuilt image. Scripts that write configuration must say so
# rather than silently producing something temporary.
#
# Splunk Cloud has no shell at all. Nothing here reaches it: configuration
# goes through the Admin Config Service or an app upload. See docs/.

# Container runtime for podman/docker transports, overridable.
: "${RUNTIME:=}"
: "${KUBECTL:=kubectl}"

t_kind()  { printf '%s' "${1%%:*}"; }
t_where() { printf '%s' "${1#*:}"; }

# Kubernetes locations carry namespace, pod and optionally a container.
_k8s_ns()        { printf '%s' "$(t_where "$1")" | cut -d/ -f1; }
_k8s_pod()       { printf '%s' "$(t_where "$1")" | cut -d/ -f2; }
_k8s_container() {
    local c
    c="$(printf '%s' "$(t_where "$1")" | cut -d/ -f3)"
    [ -n "$c" ] && printf ' -c %s' "$c"
}

t_runtime() {
    local k; k="$(t_kind "$1")"
    case "$k" in
        podman|docker) printf '%s' "${RUNTIME:-$k}" ;;
        *) printf '' ;;
    esac
}

t_valid() {
    case "$(t_kind "$1")" in
        local|ssh|podman|docker|k8s) return 0 ;;
        *) return 1 ;;
    esac
}

t_substrates() { printf 'local, ssh, podman, docker, k8s'; }

# Does a filesystem write to this target survive the instance being replaced?
t_can_persist() {
    case "$(t_kind "$1")" in
        local|ssh) return 0 ;;
        podman|docker|k8s) return 1 ;;
        *) return 1 ;;
    esac
}

# How configuration should actually be delivered on this substrate.
t_persist_advice() {
    case "$(t_kind "$1")" in
        local|ssh)
            printf 'writes to etc/apps persist' ;;
        podman|docker)
            printf 'a write into a running container is lost when the container is replaced; mount etc/apps as a volume, or bake the app into the image' ;;
        k8s)
            printf 'a write into a running pod is lost on reschedule; deliver the app as a ConfigMap, an init container, or baked into the image. With the Splunk Operator, use the app framework rather than kubectl cp' ;;
        *) printf 'unknown substrate' ;;
    esac
}

# Run a command at the target as its current default account.
t_exec() {
    local tgt="$1"; shift
    local k w rt; k="$(t_kind "$tgt")"; w="$(t_where "$tgt")"; rt="$(t_runtime "$tgt")"
    case "$k" in
        local) "$@" ;;
        ssh)   ssh -o BatchMode=yes -o ConnectTimeout=10 "$w" "$@" ;;
        podman|docker) "$rt" exec "$w" "$@" ;;
        k8s)   # shellcheck disable=SC2046
               $KUBECTL exec -n "$(_k8s_ns "$tgt")" "$(_k8s_pod "$tgt")" \
                   $(_k8s_container "$tgt") -- "$@" ;;
        *) echo "t_exec: unknown transport '$k'" >&2; return 127 ;;
    esac
}

# Run a shell snippet at the target. Kept separate from t_exec because a
# pipeline or a glob has to be evaluated at the far end, not locally.
t_sh() {
    local tgt="$1" snippet="$2"
    local k w rt; k="$(t_kind "$tgt")"; w="$(t_where "$tgt")"; rt="$(t_runtime "$tgt")"
    case "$k" in
        local) sh -c "$snippet" ;;
        ssh)   ssh -o BatchMode=yes -o ConnectTimeout=10 "$w" "$snippet" ;;
        podman|docker) "$rt" exec "$w" sh -c "$snippet" ;;
        k8s)   # shellcheck disable=SC2046
               $KUBECTL exec -n "$(_k8s_ns "$tgt")" "$(_k8s_pod "$tgt")" \
                   $(_k8s_container "$tgt") -- sh -c "$snippet" ;;
        *) return 127 ;;
    esac
}

# Run a command as a specific account. Needed because the Splunk CLI chowns
# all of SPLUNK_HOME to whoever invokes it, so calling it as the wrong
# account leaves splunkd unable to write its pid file.
t_exec_as() {
    local tgt="$1" user="$2"; shift 2
    local k w rt; k="$(t_kind "$tgt")"; w="$(t_where "$tgt")"; rt="$(t_runtime "$tgt")"
    if [ -z "$user" ]; then t_exec "$tgt" "$@"; return $?; fi
    case "$k" in
        local) if [ "$user" = "$(id -un)" ]; then "$@"; else sudo -n -u "$user" "$@"; fi ;;
        ssh)   ssh -o BatchMode=yes "$w" "sudo -n -u $user $*" ;;
        podman|docker) "$rt" exec -u "$user" "$w" "$@" ;;
        k8s)   # A pod runs as the identity its securityContext sets; kubectl
               # cannot switch account, so su is attempted and the caller is
               # told when it is not available.
               # shellcheck disable=SC2046
               $KUBECTL exec -n "$(_k8s_ns "$tgt")" "$(_k8s_pod "$tgt")" \
                   $(_k8s_container "$tgt") -- su -s /bin/sh -c "$*" "$user" ;;
        *) return 127 ;;
    esac
}

t_sh_as() {
    local tgt="$1" user="$2" snippet="$3"
    local k w rt; k="$(t_kind "$tgt")"; w="$(t_where "$tgt")"; rt="$(t_runtime "$tgt")"
    if [ -z "$user" ]; then t_sh "$tgt" "$snippet"; return $?; fi
    case "$k" in
        local) if [ "$user" = "$(id -un)" ]; then sh -c "$snippet"
               else sudo -n -u "$user" sh -c "$snippet"; fi ;;
        ssh)   ssh -o BatchMode=yes "$w" "sudo -n -u $user sh -c '$snippet'" ;;
        podman|docker) "$rt" exec -u "$user" "$w" sh -c "$snippet" ;;
        k8s)   # shellcheck disable=SC2046
               $KUBECTL exec -n "$(_k8s_ns "$tgt")" "$(_k8s_pod "$tgt")" \
                   $(_k8s_container "$tgt") -- su -s /bin/sh -c "$snippet" "$user" ;;
        *) return 127 ;;
    esac
}

# Run as the target's superuser, for ownership fixes only.
t_exec_root() {
    local tgt="$1"; shift
    local k w rt; k="$(t_kind "$tgt")"; w="$(t_where "$tgt")"; rt="$(t_runtime "$tgt")"
    case "$k" in
        local) sudo -n "$@" ;;
        ssh)   ssh -o BatchMode=yes "$w" sudo -n "$@" ;;
        podman|docker) "$rt" exec -u root "$w" "$@" ;;
        k8s)   # Only works where the pod's securityContext permits it.
               # shellcheck disable=SC2046
               $KUBECTL exec -n "$(_k8s_ns "$tgt")" "$(_k8s_pod "$tgt")" \
                   $(_k8s_container "$tgt") -- "$@" ;;
        *) return 127 ;;
    esac
}

# Copy a local path into the target.
t_copy_in() {
    local tgt="$1" src="$2" dst="$3"
    local k w rt; k="$(t_kind "$tgt")"; w="$(t_where "$tgt")"; rt="$(t_runtime "$tgt")"
    case "$k" in
        local) cp -a -- "$src" "$dst" ;;
        ssh)   scp -q -o BatchMode=yes -r -- "$src" "$w:$dst" ;;
        podman|docker) "$rt" cp "$src" "$w:$dst" ;;
        k8s)   local c; c="$(printf '%s' "$(t_where "$tgt")" | cut -d/ -f3)"
               if [ -n "$c" ]; then
                   $KUBECTL cp "$src" \
                       "$(_k8s_ns "$tgt")/$(_k8s_pod "$tgt"):$dst" -c "$c"
               else
                   $KUBECTL cp "$src" "$(_k8s_ns "$tgt")/$(_k8s_pod "$tgt"):$dst"
               fi ;;
        *) return 127 ;;
    esac
}

# Copy a path out of the target.
t_copy_out() {
    local tgt="$1" src="$2" dst="$3"
    local k w rt; k="$(t_kind "$tgt")"; w="$(t_where "$tgt")"; rt="$(t_runtime "$tgt")"
    case "$k" in
        local) cp -a -- "$src" "$dst" ;;
        ssh)   scp -q -o BatchMode=yes -r -- "$w:$src" "$dst" ;;
        podman|docker) "$rt" cp "$w:$src" "$dst" ;;
        k8s)   $KUBECTL cp "$(_k8s_ns "$tgt")/$(_k8s_pod "$tgt"):$src" "$dst" ;;
        *) return 127 ;;
    esac
}

# Is the target reachable at all? Checked before anything else, so an
# unreachable target is reported as such rather than as a missing install.
t_reachable() {
    t_sh "$1" 'exit 0' >/dev/null 2>&1
}

# The tool this substrate needs on the caller's machine.
t_required_tool() {
    case "$(t_kind "$1")" in
        local) printf '' ;;
        ssh)   printf 'ssh' ;;
        podman) printf 'podman' ;;
        docker) printf 'docker' ;;
        k8s)   printf '%s' "$KUBECTL" ;;
    esac
}

t_check_tool() {
    local tool; tool="$(t_required_tool "$1")"
    [ -z "$tool" ] && return 0
    command -v "$tool" >/dev/null 2>&1
}
