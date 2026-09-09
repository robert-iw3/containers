#!/bin/bash
# Container entrypoint for Splunk Enterprise.
#
#   splunk <args>    run a splunk CLI command
#   start-service    configure on first start, then run splunkd in the foreground
#   splunk-bash      an interactive shell with the Splunk environment loaded
#
# First-start configuration authenticates with SPLUNK_PASSWORD. A command that
# fails leaves the instance running but unconfigured, which reads exactly like
# a working one, so failures are counted and reported and the container exits
# non-zero unless SPLUNK_STRICT_CONFIG=false.
#
# The password reaches the CLI through -auth, which is visible in the process
# list inside this container. Anything that can read it is already running as
# root or splunk here.

set -uo pipefail

SPLUNK_USER="${SPLUNK_USER:-splunk}"
SPLUNK_GROUP="${SPLUNK_GROUP:-splunk}"
SPLUNK_HOME="${SPLUNK_HOME:-/opt/splunk}"
SPLUNK_ADMIN_USER="${SPLUNK_ADMIN_USER:-admin}"
STRICT="${SPLUNK_STRICT_CONFIG:-true}"

__failures=0

as_splunk() { sudo -HEu "${SPLUNK_USER}" "$@"; }

# Run a splunk CLI command that needs authentication, and record a failure
# rather than continuing as though it worked.
splunk_auth_cmd() {
    local label="$1"; shift
    if as_splunk sh -c "${SPLUNK_HOME}/bin/splunk $* -auth ${SPLUNK_ADMIN_USER}:${SPLUNK_PASSWORD}"; then
        echo "entrypoint: ${label} ok"
    else
        echo "entrypoint: ${label} FAILED (splunk $*)" >&2
        __failures=$((__failures + 1))
    fi
}

if [ "${1:-}" = 'splunk' ]; then
    shift
    exec as_splunk "${SPLUNK_HOME}/bin/splunk" "$@"

elif [ "${1:-}" = 'start-service' ]; then
    if [[ "${SPLUNK_USER}:${SPLUNK_GROUP}" != "$(stat --format %U:%G "${SPLUNK_HOME}")" ]]; then
        chown -R "${SPLUNK_USER}:${SPLUNK_GROUP}" "${SPLUNK_HOME}"
    fi

    # etc and var are declared VOLUMEs. A fresh anonymous volume over an empty
    # directory is created root-owned, and the check above does not see it
    # because it only looks at $SPLUNK_HOME itself - which the image already
    # owns correctly. splunkd then cannot create its own log directory and
    # exits after "Warning: cannot create /opt/splunk/var/log/splunk".
    for d in "${SPLUNK_HOME}/etc" "${SPLUNK_HOME}/var"; do
        [[ -d "$d" ]] || mkdir -p "$d"
        if [[ "${SPLUNK_USER}:${SPLUNK_GROUP}" != "$(stat --format %U:%G "$d")" ]]; then
            chown "${SPLUNK_USER}:${SPLUNK_GROUP}" "$d"
        fi
    done

    # A version file means this instance is already configured; first-start
    # steps run once and never again.
    __configured=false
    [[ -f ${SPLUNK_HOME}/etc/splunk.version ]] && __configured=true

    __license_ok=false
    if ! cmp --silent /var/opt/splunk/etc/splunk.version "${SPLUNK_HOME}/etc/splunk.version"; then
        cp -fR /var/opt/splunk/etc "${SPLUNK_HOME}"
        # The tarball ships only splunk-launch.conf.default; splunkd writes the
        # real file at its own first start. The image build removed etc before
        # that ever happened, so without this copy `splunk start` on the
        # forwarder execs an empty path and dies with
        # "Error calling execve(): No such file or directory" /
        # "Error launching  command" - the doubled space is the missing name.
        if [[ ! -f "${SPLUNK_HOME}/etc/splunk-launch.conf" && -f "${SPLUNK_HOME}/etc/splunk-launch.conf.default" ]]; then
            cp "${SPLUNK_HOME}/etc/splunk-launch.conf.default" "${SPLUNK_HOME}/etc/splunk-launch.conf"
        fi
        chown -R "${SPLUNK_USER}:${SPLUNK_GROUP}" "${SPLUNK_HOME}/etc"
        chown -R "${SPLUNK_USER}:${SPLUNK_GROUP}" "${SPLUNK_HOME}/var"
    else
        __license_ok=true
    fi
    tty -s && __license_ok=true
    [[ "${SPLUNK_START_ARGS:-}" == *"--accept-license"* ]] && __license_ok=true

    if [[ $__license_ok == "false" ]]; then
        cat << 'EOF'
Splunk Enterprise
=================

Accept the license agreement in one of two ways:

  - start the container interactively with -it and accept it, or
  - set SPLUNK_START_ARGS=--accept-license

Usage:

  podman run -it splunk/enterprise:10.4.2
  podman run --env SPLUNK_START_ARGS="--accept-license" splunk/enterprise:10.4.2

EOF
        exit 1
    fi

    # Staged configuration and certificates, applied before splunkd starts.
    #
    # Neither can be bind-mounted at its final path. A mount over
    # etc/system/local hides passwords.conf, which holds the seeded admin
    # credential, and a mount over etc/auth/mycerts carries the host's
    # ownership: that maps to root in the container while splunkd runs as
    # splunk, so 0600 keys are unreadable and Splunk Web comes up with SSL
    # enabled and no usable certificate, answering nothing at all.
    #
    # Mount them here instead and they are copied in, owned by splunk, before
    # anything reads them - so no restart is needed to apply them.
    # Refuse to stage into an etc tree that was never populated. The copy above
    # is what creates it, and staging into an empty tree produces directories
    # that look right and a Splunk that cannot start.
    #
    # The sentinel is system/default, not splunk-launch.conf: the image ships
    # only splunk-launch.conf.default, and Splunk writes the real file itself
    # at first start.
    if [[ -d /staged/conf || -d /staged/certs ]] && [[ ! -d "${SPLUNK_HOME}/etc/system/default" ]]; then
        echo "entrypoint: ${SPLUNK_HOME}/etc is not populated; refusing to stage" >&2
        exit 1
    fi

    stage_dir() { # stage_dir <src> <dst> <mode>
        local src="$1" dst="$2" mode="$3"
        [[ -d "$src" ]] || return 0
        mkdir -p "$dst"
        cp -f "$src"/* "$dst"/ 2>/dev/null
        chown -R "${SPLUNK_USER}:${SPLUNK_GROUP}" "$dst"
        [[ -n "$mode" ]] && chmod "$mode" "$dst"/* 2>/dev/null
        echo "entrypoint: staged $(basename "$src") -> ${dst}"
    }
    # Mounted OUTSIDE $SPLUNK_HOME. Splunk's own start reverts ownership with a
    # recursive chown of $SPLUNK_HOME; a read-only mount inside it makes that
    # chown fail, and Splunk then aborts with "Error calling execve()" - which
    # names nothing that would lead you back here.
    stage_dir /staged/conf  "${SPLUNK_HOME}/etc/system/local" ""
    stage_dir /staged/certs "${SPLUNK_HOME}/etc/auth/mycerts" "600"

    # Every authenticated command below needs this. Without it they all fail
    # one by one after Splunk is already up, so refuse before starting.
    if [[ $__configured == "false" && -z "${SPLUNK_PASSWORD:-}" ]]; then
        echo "entrypoint: SPLUNK_PASSWORD is required on first start" >&2
        exit 1
    fi

    if [[ $__configured == "false" ]]; then
        if [[ -n "${SPLUNK_BEFORE_START_CMD:-}" ]]; then
            as_splunk sh -c "${SPLUNK_HOME}/bin/splunk ${SPLUNK_BEFORE_START_CMD}"
        fi
        for n in {1..30}; do
            cmd="$(eval echo "\${SPLUNK_BEFORE_START_CMD_${n}:-}")"
            [[ -n "$cmd" ]] || break
            as_splunk sh -c "${SPLUNK_HOME}/bin/splunk ${cmd}"
        done
    fi

    # First start must be non-interactive. Without a seeded password splunkd
    # prompts for an administrator username on stdin and blocks there forever:
    # the container reports Up, its healthcheck never passes, and the logs show
    # "Please enter an administrator username" with no further output.
    # SPLUNK_PASSWORD alone does not do this - it has to be seeded.
    if [[ $__configured == "false" ]]; then
        as_splunk "${SPLUNK_HOME}/bin/splunk" start ${SPLUNK_START_ARGS:-} \
            --answer-yes --no-prompt --seed-passwd "${SPLUNK_PASSWORD}"
    else
        as_splunk "${SPLUNK_HOME}/bin/splunk" start ${SPLUNK_START_ARGS:-} \
            --answer-yes --no-prompt
    fi
    trap 'as_splunk "${SPLUNK_HOME}/bin/splunk" stop' SIGINT SIGTERM EXIT

    if [[ $__configured == "false" ]]; then
        __restart_required=false

        if [[ "${SPLUNK_ENABLE_DEPLOY_SERVER:-}" == "true" ]]; then
            splunk_auth_cmd "enable deploy-server" "enable deploy-server"
            __restart_required=true
        fi

        if [[ -n "${SPLUNK_DEPLOYMENT_SERVER:-}" ]]; then
            splunk_auth_cmd "set deploy-poll" "set deploy-poll ${SPLUNK_DEPLOYMENT_SERVER}"
            __restart_required=true
        fi

        if [[ "$__restart_required" == "true" ]]; then
            as_splunk sh -c "${SPLUNK_HOME}/bin/splunk restart"
        fi

        # Receiving port. Its silent absence is the failure that looks like a
        # forwarder problem for the next several hours.
        if [[ -n "${SPLUNK_ENABLE_LISTEN:-}" ]]; then
            splunk_auth_cmd "enable listen ${SPLUNK_ENABLE_LISTEN}" \
                "enable listen ${SPLUNK_ENABLE_LISTEN} ${SPLUNK_ENABLE_LISTEN_ARGS:-}"
        fi

        if [[ -n "${SPLUNK_FORWARD_SERVER:-}" ]]; then
            splunk_auth_cmd "add forward-server" \
                "add forward-server ${SPLUNK_FORWARD_SERVER} ${SPLUNK_FORWARD_SERVER_ARGS:-}"
        fi
        for n in {1..10}; do
            server="$(eval echo "\${SPLUNK_FORWARD_SERVER_${n}:-}")"
            [[ -n "$server" ]] || break
            args="$(eval echo "\${SPLUNK_FORWARD_SERVER_${n}_ARGS:-}")"
            splunk_auth_cmd "add forward-server ${n}" "add forward-server ${server} ${args}"
        done

        if [[ -n "${SPLUNK_ADD:-}" ]]; then
            splunk_auth_cmd "add ${SPLUNK_ADD}" "add ${SPLUNK_ADD}"
        fi
        for n in {1..30}; do
            item="$(eval echo "\${SPLUNK_ADD_${n}:-}")"
            [[ -n "$item" ]] || break
            splunk_auth_cmd "add ${item}" "add ${item}"
        done

        if [[ -n "${SPLUNK_CMD:-}" ]]; then
            splunk_auth_cmd "cmd" "${SPLUNK_CMD}"
        fi
        for n in {1..30}; do
            item="$(eval echo "\${SPLUNK_CMD_${n}:-}")"
            [[ -n "$item" ]] || break
            splunk_auth_cmd "cmd ${n}" "${item}"
        done

        if [[ $__failures -gt 0 ]]; then
            echo "entrypoint: ${__failures} first-start configuration command(s) failed" >&2
            if [[ "$STRICT" != "false" ]]; then
                echo "entrypoint: refusing to run unconfigured; set SPLUNK_STRICT_CONFIG=false to override" >&2
                exit 1
            fi
        fi
    fi

    as_splunk tail -n 0 -f "${SPLUNK_HOME}/var/log/splunk/splunkd_stderr.log" &
    __tail_pid=$!

    # Follow splunkd, not the tail. Waiting on the tail alone keeps the
    # container reported as up after splunkd has gone.
    #
    # Three consecutive failures, not one. `splunk restart` inside the
    # container - applying configuration, rotating a certificate - leaves a
    # gap of a few seconds where status is non-zero, and exiting on the first
    # sample turns an administrative restart into a container that never comes
    # back.
    __down=0
    while true; do
        if as_splunk "${SPLUNK_HOME}/bin/splunk" status >/dev/null 2>&1; then
            __down=0
        else
            __down=$((__down + 1))
            [[ $__down -ge 3 ]] && break
        fi
        sleep 10
    done
    echo "entrypoint: splunkd is no longer running" >&2
    kill "${__tail_pid}" 2>/dev/null
    exit 1

elif [ "${1:-}" = 'splunk-bash' ]; then
    exec sudo -u "${SPLUNK_USER}" /bin/bash --init-file "${SPLUNK_HOME}/bin/setSplunkEnv"

else
    exec "$@"
fi
