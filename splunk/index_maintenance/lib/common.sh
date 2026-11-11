# Shared helpers for the index maintenance scripts. Sourced, not run.
#
# Everything here exists to make one decision safely: which Splunk am I
# talking to, and as whom. Running the Splunk CLI as root leaves root-owned
# files in $SPLUNK_HOME that splunkd cannot then rewrite, so the account is
# resolved from the installation itself rather than assumed.

set -uo pipefail

IM_CONTAINER=""
IM_SPLUNK_HOME="${SPLUNK_HOME:-/opt/splunk}"
IM_USER=""
IM_AUTH=""
IM_YES=0
IM_DRY=0

# --- argument parsing shared by every script ----------------------------
# Each script calls im_parse_common "$@" and then handles what is left in
# IM_REST. Keeping the connection flags in one place means every script
# takes them the same way.
IM_REST=()
im_parse_common() {
    IM_REST=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --container)   IM_CONTAINER="${2:-}"; shift 2 ;;
            --splunk-home) IM_SPLUNK_HOME="${2:-}"; shift 2 ;;
            --user)        IM_USER="${2:-}"; shift 2 ;;
            --auth-file)   im_read_auth "${2:-}"; shift 2 ;;
            --yes|-y)      IM_YES=1; shift ;;
            --dry-run|-n)  IM_DRY=1; shift ;;
            *)             IM_REST+=("$1"); shift ;;
        esac
    done
}

# Credentials are read from a file or the environment, never from the command
# line, where they would be visible in the process table and in shell history.
im_read_auth() {
    local f="${1:-}"
    [ -n "$f" ] || im_die "--auth-file needs a path"
    [ -r "$f" ] || im_die "cannot read $f"
    IM_AUTH="$(sed -n 1p "$f")"
    [ -n "$IM_AUTH" ] || im_die "$f is empty; it should hold one line of user:password"
}

im_auth_from_env() {
    [ -n "$IM_AUTH" ] && return 0
    [ -n "${SPLUNK_AUTH:-}" ] && { IM_AUTH="$SPLUNK_AUTH"; return 0; }
    return 1
}

# --- output -------------------------------------------------------------
im_die()  { printf 'FAIL: %s\n' "$*" >&2; exit 2; }
im_warn() { printf '  !! %s\n' "$*" >&2; }
im_say()  { printf '  %s\n' "$*"; }
im_head() { printf '\n== %s ==\n' "$*"; }

# A number that may be missing. An arithmetic comparison against an empty
# string or a word aborts the script under set -u, which turns a missing
# reading into a crash somewhere unrelated.
im_num() {
    case "${1:-}" in
        ''|*[!0-9-]*) printf '0' ;;
        *)            printf '%s' "$1" ;;
    esac
}

# --- running commands ---------------------------------------------------
# Resolve the account that owns the installation. Doing this once and
# reporting it means a script never silently runs as the wrong user.
im_resolve_user() {
    [ -n "$IM_USER" ] && return 0
    if [ -n "$IM_CONTAINER" ]; then
        IM_USER="$(podman exec "$IM_CONTAINER" stat -c '%U' "$IM_SPLUNK_HOME/etc" 2>/dev/null \
                   | tr -d '\r')"
    else
        IM_USER="$(stat -c '%U' "$IM_SPLUNK_HOME/etc" 2>/dev/null)"
    fi
    [ -n "$IM_USER" ] || im_die "cannot find $IM_SPLUNK_HOME/etc -- is --splunk-home right?"
    if [ "$IM_USER" = "root" ]; then
        im_warn "$IM_SPLUNK_HOME/etc is owned by root; the CLI will run as root"
        im_warn "and may leave files splunkd cannot rewrite."
    fi
}

# Run a shell command against the installation.
im_run() {
    if [ -n "$IM_CONTAINER" ]; then
        podman exec -u "$IM_USER" "$IM_CONTAINER" sh -c "$1"
    else
        sh -c "$1"
    fi
}

# Run one as root, for the few things that need it (chown after a copy in).
im_run_root() {
    if [ -n "$IM_CONTAINER" ]; then
        podman exec -u root "$IM_CONTAINER" sh -c "$1"
    else
        sh -c "$1"
    fi
}

# The Splunk CLI. Commands that reach splunkd need credentials; btool and
# the service controls do not.
im_splunk() {
    im_run "$IM_SPLUNK_HOME/bin/splunk $1" 2>&1 | grep -v 'Server Certificate Hostname Validation'
}

im_splunk_auth() {
    im_auth_from_env || im_die \
        "this needs credentials: pass --auth-file <file> or set SPLUNK_AUTH=user:password"
    # The credential is passed through the environment of the remote shell
    # rather than interpolated into the command string, so it does not appear
    # in the container's process list.
    if [ -n "$IM_CONTAINER" ]; then
        podman exec -u "$IM_USER" -e "IM_A=$IM_AUTH" "$IM_CONTAINER" sh -c \
            "$IM_SPLUNK_HOME/bin/splunk $1 -auth \"\$IM_A\"" 2>&1 \
            | grep -v 'Server Certificate Hostname Validation'
    else
        IM_A="$IM_AUTH" sh -c \
            "$IM_SPLUNK_HOME/bin/splunk $1 -auth \"\$IM_A\"" 2>&1 \
            | grep -v 'Server Certificate Hostname Validation'
    fi
}

# Ask for credentials when they are needed and none were supplied. The
# password is read with the terminal echo off and is not written anywhere.
im_prompt_auth() {
    im_auth_from_env && return 0
    if [ ! -t 0 ]; then
        im_die "credentials needed and no terminal to ask on: pass --auth-file <file> or set SPLUNK_AUTH=user:password"
    fi
    local u p
    printf '  Splunk username: ' >&2
    read -r u
    [ -n "$u" ] || im_die "no username given"
    printf '  Password for %s: ' "$u" >&2
    stty -echo 2>/dev/null || true
    read -r p
    stty echo 2>/dev/null || true
    printf '\n' >&2
    [ -n "$p" ] || im_die "no password given"
    IM_AUTH="$u:$p"
    unset p
}

# Checked before the first search rather than inside it: im_die in a command
# substitution exits only the subshell, so the caller carries on and reports a
# second, less useful failure after the real one.
im_require_auth() {
    im_auth_from_env && return 0
    im_prompt_auth
}

# Does the credential actually work? A wrong password otherwise surfaces as
# an empty search result, which reads like an empty index.
im_auth_works() {
    local out
    out="$(im_splunk_auth "search 'index=_internal | head 1 | stats count' -output csv -preview false" 2>&1)"
    case "$out" in
        *"Login failed"*|*"Unauthorized"*|*"username and password"*) return 1 ;;
    esac
    printf '%s' "$out" | grep -c . >/dev/null 2>&1
    case "$out" in *count*) return 0 ;; esac
    return 1
}

im_splunkd_running() {
    # grep -c rather than grep -q: closing the pipe early makes the writer
    # take SIGPIPE, and the exit status then describes the signal instead of
    # the match.
    local n
    n="$(im_run "$IM_SPLUNK_HOME/bin/splunk status 2>/dev/null | grep -c 'is running'" || true)"
    [ "$(im_num "$n")" -gt 0 ]
}

im_stop()  { im_say "stopping splunkd";  im_run "$IM_SPLUNK_HOME/bin/splunk stop  >/dev/null 2>&1" || true; }
im_start() { im_say "starting splunkd";  im_run "$IM_SPLUNK_HOME/bin/splunk start >/dev/null 2>&1" || true; }

# --- confirmation -------------------------------------------------------
# Anything that cannot be undone asks, unless the caller already said yes.
im_confirm() {
    [ "$IM_YES" = "1" ] && return 0
    printf '\n  %s\n  Type yes to continue: ' "$1"
    local a; read -r a
    [ "$a" = "yes" ] || { echo "  stopped."; exit 1; }
}

# --- index facts --------------------------------------------------------
# Read from btool, which reports the merged configuration actually in force
# rather than whatever one file happens to say.
im_index_exists() {
    local n
    n="$(im_run "$IM_SPLUNK_HOME/bin/splunk btool indexes list '$1' 2>/dev/null | grep -c '^\['" || true)"
    [ "$(im_num "$n")" -gt 0 ]
}

im_index_setting() {
    # $1 index, $2 setting
    im_run "$IM_SPLUNK_HOME/bin/splunk btool indexes list '$1' 2>/dev/null \
            | sed -n 's/^$2 *= *//p' | sed -n 1p" | tr -d '\r'
}

im_index_path() {
    local p; p="$(im_index_setting "$1" homePath)"
    # Paths are written with volume references and $SPLUNK_DB.
    p="${p//\$SPLUNK_DB/$IM_SPLUNK_HOME/var/lib/splunk}"
    printf '%s' "$p"
}
