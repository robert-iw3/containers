# Splunk discovery and the privilege guard. Sourced by every script in this tool.
#
# THERE IS ONE CODE PATH: the local one. A script in this tool always runs on the
# instance it is assessing, as the account that owns the installation. Assessing a
# container is not a second code path - bin/in-container.sh copies this tooling
# into the container and runs the same scripts there. That is deliberate: two
# paths means the one you test is not the one that runs in production.
#
# Provides, after target_init:
#   SPLUNK_HOME  resolved installation directory
#   SP           the splunk binary
#   sh_in CMD    run CMD
#   sp ARGS...   run the splunk CLI

SPLUNK_HOME="${SPLUNK_HOME:-}"
SP=""
TGT_SPLUNK_HOME_HINT="${TGT_SPLUNK_HOME_HINT:-}"
# Preserved if a caller set it before sourcing: the option loop may run first.
TGT_ALLOW_WRONG_USER="${TGT_ALLOW_WRONG_USER:-0}"
TGT_ORIGINAL_ARGS="${TGT_ORIGINAL_ARGS:-}"

sh_in() { sh -c "$1" 2>/dev/null; }
sp()    { sh_in "'$SP' $*"; }

target_find_home() {
    if [ -n "$TGT_SPLUNK_HOME_HINT" ]; then
        if [ -x "${TGT_SPLUNK_HOME_HINT}/bin/splunk" ]; then
            SPLUNK_HOME="$TGT_SPLUNK_HOME_HINT"; return 0
        fi
        printf 'no splunk binary under %s/bin\n' "$TGT_SPLUNK_HOME_HINT" >&2
        return 3
    fi
    local c
    for c in /opt/splunk /opt/splunkforwarder /Applications/Splunk \
             /usr/local/splunk /usr/local/splunkforwarder \
             "C:/Program Files/Splunk" "C:/Program Files/SplunkUniversalForwarder" \
             "${SPLUNK_HOME:-}"; do
        [ -n "$c" ] || continue
        if [ -x "${c}/bin/splunk" ] || [ -x "${c}/bin/splunk.exe" ]; then
            SPLUNK_HOME="$c"; return 0
        fi
    done
    printf 'no Splunk installation found\n' >&2
    printf '  looked in /opt/splunk, /opt/splunkforwarder, /Applications/Splunk,\n' >&2
    printf '  /usr/local/splunk, /usr/local/splunkforwarder and $SPLUNK_HOME\n' >&2
    printf '  pass --splunk-home PATH if the installation is elsewhere\n' >&2
    return 3
}

target_check_user() {
    # The Splunk CLI writes as whoever runs it. One invocation by the wrong account
    # leaves files under etc/ owned by that account - etc/system/metadata/local.meta
    # is the measured case - and splunkd then fails to start at its next restart.
    #
    # This refuses rather than dropping privileges itself. An operator told the exact
    # command keeps control of what runs as whom, and a tool that silently su's is
    # harder to audit than one that stops and explains.
    [ "$TGT_ALLOW_WRONG_USER" -eq 1 ] && return 0

    local owner me
    owner="$(ls -ld "${SPLUNK_HOME}/etc" 2>/dev/null | awk '{print $3}')"
    me="$(id -un 2>/dev/null)"
    [ -n "$owner" ] || return 0          # cannot tell; do not block on a guess
    [ -n "$me" ] || return 0
    [ "$owner" = "$me" ] && return 0

    printf '\n  REFUSING TO RUN as %s against an installation owned by %s.\n\n' "$me" "$owner" >&2
    printf '  The Splunk CLI writes as whoever runs it. One invocation as the wrong\n' >&2
    printf '  account leaves files it owns under %s/etc, and splunkd\n' "$SPLUNK_HOME" >&2
    printf '  then fails to start at its next restart.\n\n' >&2
    printf '  Run it as the account that owns the installation:\n\n' >&2
    if [ "$me" = "root" ]; then
        printf '      su - %s -c "%s %s"\n\n' "$owner" "$0" "$TGT_ORIGINAL_ARGS" >&2
    else
        printf '      sudo -u %s %s %s\n\n' "$owner" "$0" "$TGT_ORIGINAL_ARGS" >&2
    fi
    printf '  To override, which is not advised: --allow-wrong-user\n' >&2
    return 3
}

target_init() {
    target_find_home || return 3
    SP="${SPLUNK_HOME}/bin/splunk"
    [ -x "$SP" ] || SP="${SPLUNK_HOME}/bin/splunk.exe"
    target_check_user || return 3
    return 0
}
