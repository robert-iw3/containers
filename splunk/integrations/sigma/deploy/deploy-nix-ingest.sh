#!/usr/bin/env bash
# Deploy Splunk_TA_nix and Linux audit collection to a Splunk deployment.
#
# Nothing about any particular instance lives in this file. A target config
# supplies the hosts, transport and names; see targets/example.conf. Run as:
#
#   ./deploy-nix-ingest.sh --target targets/mysite.conf            # dry run
#   APPLY=1 ./deploy-nix-ingest.sh --target targets/mysite.conf
#
# Three transports, because a Splunk instance is not always a container:
#
#   local      this machine, SPLUNK_HOME on local disk
#   ssh        a remote host over ssh
#   podman     a container (docker works too, set RUNTIME=docker)
#
# Split of responsibilities, as a real deployment does it:
#   collector  the add-on plus monitor inputs
#   indexer    the add-on for parsing, and the index definition
# Point both roles at the same target for a single-instance deployment.
#
# Two things reading the add-on makes necessary, which a naive install misses:
#
#   1. Splunk_TA_nix never assigns the linux_audit sourcetype. It ships no
#      source:: stanza for it and never mentions audit.log, so the sourcetype
#      must be set explicitly on the monitor stanza. Left to autodetection it
#      gets the wrong sourcetype and none of the add-on's CIM work runs.
#   2. The add-on's own "auditd" sourcetype comes from rlog.sh piping
#      ausearch -i, whose interpreted output resolves uid to a name and drops
#      the raw a0/a1 argument fields. Detection content written against raw
#      auditd records needs a plain file monitor as linux_audit, so the
#      scripted input is left off.
#
# Idempotent. Writes only into etc/apps, never etc/system/local. Records
# btool check before and after so a configuration baseline can be re-verified.
set -euo pipefail

TARGET=""
APPLY="${APPLY:-0}"
WORK="${WORK:-}"

while [ $# -gt 0 ]; do
    case "$1" in
        --target) TARGET="${2:-}"; shift 2 ;;
        --apply)  APPLY=1; shift ;;
        -h|--help) sed -n '2,36p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

[ -n "$TARGET" ] || { echo "FAIL: --target <config> is required" >&2; exit 2; }
[ -f "$TARGET" ] || { echo "FAIL: target config not found: $TARGET" >&2; exit 2; }

# ------------------------------------------------------------ defaults

RUNTIME="${RUNTIME:-podman}"

# Roles. Each is TRANSPORT:LOCATION, e.g. podman:splunk-idx,
# ssh:splunk@idx01.example.com, or local:/opt/splunk.
INDEXER_TARGET=""
COLLECTOR_TARGET=""

TA_PACKAGE=""
TA_SHA256=""

INDEX_NAME="nix_audit"
INDEX_APP="splunk_ta_nix_indexes"
INPUTS_APP="splunk_ta_nix_inputs"
INDEX_MAX_MB="4096"
INDEX_RETENTION_SECS="2592000"

# Standard Linux audit sources. sourcetype is explicit on every one.
LOG_SOURCES=(
    "/var/log/audit/audit.log:linux_audit"
    "/var/log/secure:linux_secure"
    "/var/log/auth.log:linux_secure"
    "/var/log/messages:syslog"
    "/var/log/syslog:syslog"
)

# Staging is a container workaround, not the normal path: a forwarder on the
# host reads /var/log directly. auto turns it on only for container
# transports, where the logs are outside the container.
STAGE_LOGS="auto"
STAGE_FROM=""
RESTART="1"

# shellcheck source=/dev/null
. "$TARGET"

[ -n "$INDEXER_TARGET" ]   || { echo "FAIL: target sets no INDEXER_TARGET" >&2; exit 2; }
[ -n "$COLLECTOR_TARGET" ] || { echo "FAIL: target sets no COLLECTOR_TARGET" >&2; exit 2; }
[ -n "$TA_PACKAGE" ]       || { echo "FAIL: target sets no TA_PACKAGE" >&2; exit 2; }

WORK="${WORK:-$(mktemp -d)}"

say() { printf '\n== %s\n' "$*"; }
run() { if [ "$APPLY" = "1" ]; then "$@"; else printf '  [dry-run] %s\n' "$*"; fi; }

[ "$APPLY" = "1" ] || echo "DRY RUN. Nothing will change. Re-run with APPLY=1."

# ------------------------------------------------------- transport layer

t_kind() { printf '%s' "${1%%:*}"; }
t_where() { printf '%s' "${1#*:}"; }

# Service account. The Splunk CLI chowns all of SPLUNK_HOME to whoever
# invokes it, so invoking it as the wrong account leaves splunkd unable to
# write its own pid file. For a container the account is read from its
# config rather than assumed.
svc_user() {
    local tgt="$1" kind where
    kind="$(t_kind "$tgt")"; where="$(t_where "$tgt")"
    case "$kind" in
        podman|docker)
            local u
            u="$($RUNTIME inspect "$where" --format '{{.Config.User}}' 2>/dev/null || true)"
            printf '%s' "${u:-splunk}" ;;
        *) printf '%s' "${SPLUNK_USER:-splunk}" ;;
    esac
}

# Run a command in the target's context, as the service account.
t_exec() {
    local tgt="$1"; shift
    local kind where user
    kind="$(t_kind "$tgt")"; where="$(t_where "$tgt")"; user="$(svc_user "$tgt")"
    case "$kind" in
        local)  "$@" ;;
        ssh)    ssh -o BatchMode=yes "$where" "$@" ;;
        podman|docker) $RUNTIME exec -u "$user" "$where" "$@" ;;
        *) echo "FAIL: unknown transport '$kind'" >&2; return 1 ;;
    esac
}

# Run as the superuser of the target, for ownership fixes only.
t_exec_root() {
    local tgt="$1"; shift
    local kind where
    kind="$(t_kind "$tgt")"; where="$(t_where "$tgt")"
    case "$kind" in
        local)  sudo -n "$@" ;;
        ssh)    ssh -o BatchMode=yes "$where" sudo -n "$@" ;;
        podman|docker) $RUNTIME exec -u root "$where" "$@" ;;
    esac
}

# Copy a local path into the target.
t_copy() {
    local tgt="$1" src="$2" dst="$3"
    local kind where
    kind="$(t_kind "$tgt")"; where="$(t_where "$tgt")"
    case "$kind" in
        local)  cp -a "$src" "$dst" ;;
        ssh)    scp -q -o BatchMode=yes -r "$src" "$where:$dst" ;;
        podman|docker) $RUNTIME cp "$src" "$where:$dst" ;;
    esac
}

# SPLUNK_HOME for a role. A forwarder and a full instance differ, so it is
# probed rather than guessed.
t_home() {
    local tgt="$1"
    if [ -n "${SPLUNK_HOME_OVERRIDE:-}" ]; then printf '%s' "$SPLUNK_HOME_OVERRIDE"; return; fi
    local kind where
    kind="$(t_kind "$tgt")"; where="$(t_where "$tgt")"
    if [ "$kind" = "local" ] && [ -d "$where" ]; then printf '%s' "$where"; return; fi
    for h in /opt/splunk /opt/splunkforwarder; do
        if t_exec "$tgt" test -x "$h/bin/splunk" 2>/dev/null; then printf '%s' "$h"; return; fi
    done
    printf '%s' "/opt/splunk"
}

stage_enabled() {
    case "$STAGE_LOGS" in
        yes) return 0 ;;
        no)  return 1 ;;
        auto)
            case "$(t_kind "$COLLECTOR_TARGET")" in
                podman|docker) return 0 ;;
                *) return 1 ;;
            esac ;;
    esac
}

# --------------------------------------------------------------- preflight

say "Preflight"
IDX_HOME="$(t_home "$INDEXER_TARGET")"
COL_HOME="$(t_home "$COLLECTOR_TARGET")"
printf '  indexer   %-34s home=%s user=%s\n' "$INDEXER_TARGET"   "$IDX_HOME" "$(svc_user "$INDEXER_TARGET")"
printf '  collector %-34s home=%s user=%s\n' "$COLLECTOR_TARGET" "$COL_HOME" "$(svc_user "$COLLECTOR_TARGET")"
printf '  index=%s  staging=%s\n' "$INDEX_NAME" "$(stage_enabled && echo on || echo off)"

for tgt in "$INDEXER_TARGET" "$COLLECTOR_TARGET"; do
    if ! t_exec "$tgt" test -x "$(t_home "$tgt")/bin/splunk"; then
        echo "FAIL: no splunk binary reachable at $tgt" >&2; exit 1
    fi
done

[ -f "$TA_PACKAGE" ] || { echo "FAIL: TA_PACKAGE not found: $TA_PACKAGE" >&2; exit 1; }

# Verify against the configured hash, or a sidecar if the target gave none.
if [ -z "$TA_SHA256" ] && [ -f "${TA_PACKAGE}.sha256" ]; then
    TA_SHA256="$(cut -d' ' -f1 < "${TA_PACKAGE}.sha256")"
fi
actual="$(sha256sum "$TA_PACKAGE" | cut -d' ' -f1)"
if [ -n "$TA_SHA256" ]; then
    if [ "$actual" != "$TA_SHA256" ]; then
        echo "FAIL: checksum mismatch for $TA_PACKAGE" >&2
        echo "      expected $TA_SHA256" >&2
        echo "      actual   $actual" >&2
        exit 1
    fi
    echo "  package sha256 verified"
else
    echo "  WARNING: no TA_SHA256 and no .sha256 sidecar; integrity unverified"
    echo "           package sha256: $actual"
fi

if tar -tzf "$TA_PACKAGE" | grep -qE '^/|\.\.'; then
    echo "FAIL: package contains absolute or parent paths" >&2; exit 1
fi

say "Baseline"
t_exec "$INDEXER_TARGET" "$IDX_HOME/bin/splunk" btool check \
    > "$WORK/btool-check.before.txt" 2>&1 || true
printf '  indexer btool check: %s line(s)\n' "$(wc -l < "$WORK/btool-check.before.txt")"
t_exec "$INDEXER_TARGET" "$IDX_HOME/bin/splunk" btool indexes list 2>/dev/null \
    | grep '^\[' | sort > "$WORK/indexes.before.txt" || true
t_exec "$INDEXER_TARGET" sh -c "ls -1 $IDX_HOME/etc/apps" > "$WORK/apps-indexer.before.txt" 2>/dev/null || true
printf '  indexes: %s  apps: %s\n' \
    "$(wc -l < "$WORK/indexes.before.txt")" "$(wc -l < "$WORK/apps-indexer.before.txt")"

say "Unpack the add-on"
mkdir -p "$WORK/ta"
tar -xzf "$TA_PACKAGE" -C "$WORK/ta"
TA_DIR="$(find "$WORK/ta" -maxdepth 1 -mindepth 1 -type d | head -1)"
TA_NAME="$(basename "$TA_DIR")"
[ -n "$TA_DIR" ] || { echo "FAIL: package has no top-level directory" >&2; exit 1; }
printf '  %s version %s\n' "$TA_NAME" "$(sed -n 1p "$TA_DIR/VERSION" 2>/dev/null || echo unknown)"

# ----------------------------------------------------------- indexer

say "Indexer: install $TA_NAME for parsing"
run t_exec "$INDEXER_TARGET" mkdir -p "$IDX_HOME/etc/apps"
run t_copy "$INDEXER_TARGET" "$TA_DIR" "$IDX_HOME/etc/apps/$TA_NAME"
# podman cp will not create a missing parent, so every destination exists first.
run t_exec "$INDEXER_TARGET" mkdir -p \
    "$IDX_HOME/etc/apps/$TA_NAME/local" \
    "$IDX_HOME/etc/apps/$INDEX_APP/local" \
    "$IDX_HOME/etc/apps/$INDEX_APP/metadata"

cat > "$WORK/indexer-inputs.conf" <<'CONF'
# This instance uses the add-on for parsing only. Every input it ships is
# disabled so the indexer does not start collecting from itself.
[default]
disabled = 1
CONF
run t_copy "$INDEXER_TARGET" "$WORK/indexer-inputs.conf" \
    "$IDX_HOME/etc/apps/$TA_NAME/local/inputs.conf"

say "Indexer: define index $INDEX_NAME"
cat > "$WORK/indexes.conf" <<CONF
# Linux audit data.
[$INDEX_NAME]
homePath   = \$SPLUNK_DB/$INDEX_NAME/db
coldPath   = \$SPLUNK_DB/$INDEX_NAME/colddb
thawedPath = \$SPLUNK_DB/$INDEX_NAME/thaweddb
maxTotalDataSizeMB = $INDEX_MAX_MB
frozenTimePeriodInSecs = $INDEX_RETENTION_SECS
CONF
cat > "$WORK/index-app.conf" <<CONF
[install]
state = enabled

[ui]
is_visible = 0
label = $INDEX_APP
CONF
cat > "$WORK/local.meta" <<'META'
[]
access = read : [ * ], write : [ admin ]
export = system
META
run t_copy "$INDEXER_TARGET" "$WORK/indexes.conf"   "$IDX_HOME/etc/apps/$INDEX_APP/local/indexes.conf"
run t_copy "$INDEXER_TARGET" "$WORK/index-app.conf" "$IDX_HOME/etc/apps/$INDEX_APP/local/app.conf"
run t_copy "$INDEXER_TARGET" "$WORK/local.meta"     "$IDX_HOME/etc/apps/$INDEX_APP/metadata/local.meta"
run t_exec_root "$INDEXER_TARGET" chown -R \
    "$(svc_user "$INDEXER_TARGET"):$(svc_user "$INDEXER_TARGET")" \
    "$IDX_HOME/etc/apps/$TA_NAME" "$IDX_HOME/etc/apps/$INDEX_APP"

# ---------------------------------------------------------- collector

say "Collector: install $TA_NAME for collection"
run t_exec "$COLLECTOR_TARGET" mkdir -p "$COL_HOME/etc/apps"
run t_copy "$COLLECTOR_TARGET" "$TA_DIR" "$COL_HOME/etc/apps/$TA_NAME"
run t_exec "$COLLECTOR_TARGET" mkdir -p "$COL_HOME/etc/apps/$INPUTS_APP/local"

MONITOR_BASE=""
if stage_enabled; then
    STAGE_DIR="$COL_HOME/etc/apps/$INPUTS_APP/staged"
    say "Collector: stage log data into $STAGE_DIR"
    echo "  (the collector cannot see the host's /var/log, so content is copied in;"
    echo "   the events are genuine, only the transport is a copy)"
    run t_exec "$COLLECTOR_TARGET" mkdir -p "$STAGE_DIR"
    MONITOR_BASE="$STAGE_DIR"
    staged=0
    for entry in "${LOG_SOURCES[@]}"; do
        src="${entry%%:*}"
        [ -n "$STAGE_FROM" ] && src="$STAGE_FROM/$(basename "$src")"
        if [ -r "$src" ]; then
            printf '  %s (%s bytes)\n' "$src" "$(stat -c%s "$src")"
            run t_copy "$COLLECTOR_TARGET" "$src" "$STAGE_DIR/$(basename "$src")"
            staged=$((staged+1))
        else
            printf '  skip %s (not readable)\n' "$src"
        fi
    done
    if [ "$staged" -eq 0 ]; then
        echo "FAIL: no source log readable; nothing to collect" >&2; exit 1
    fi
fi

say "Collector: monitor inputs"
{
    echo "# Linux audit collection. sourcetype is explicit on every stanza:"
    echo "# $TA_NAME assigns linux_secure by source:: but has nothing at all"
    echo "# for linux_audit, so autodetection would pick the wrong one."
    if stage_enabled; then
        echo "#"
        echo "# crcSalt makes each path distinct to the fishbucket, so restaging"
        echo "# a file re-reads it instead of being treated as already seen."
    fi
    for entry in "${LOG_SOURCES[@]}"; do
        src="${entry%%:*}"; st="${entry##*:}"
        path="$src"
        if stage_enabled; then
            path="$MONITOR_BASE/$(basename "$src")"
            # Only emit a stanza for something that was actually staged.
            [ -r "$src" ] || continue
        fi
        echo
        echo "[monitor://$path]"
        echo "sourcetype = $st"
        echo "index = $INDEX_NAME"
        echo "disabled = 0"
        stage_enabled && echo "crcSalt = <SOURCE>"
    done
} > "$WORK/collector-inputs.conf"

cat > "$WORK/inputs-app.conf" <<CONF
[install]
state = enabled

[ui]
is_visible = 0
label = $INPUTS_APP
CONF
run t_copy "$COLLECTOR_TARGET" "$WORK/collector-inputs.conf" \
    "$COL_HOME/etc/apps/$INPUTS_APP/local/inputs.conf"
run t_copy "$COLLECTOR_TARGET" "$WORK/inputs-app.conf" \
    "$COL_HOME/etc/apps/$INPUTS_APP/local/app.conf"
run t_exec_root "$COLLECTOR_TARGET" chown -R \
    "$(svc_user "$COLLECTOR_TARGET"):$(svc_user "$COLLECTOR_TARGET")" \
    "$COL_HOME/etc/apps/$TA_NAME" "$COL_HOME/etc/apps/$INPUTS_APP"

# ------------------------------------------------------------- restart

if [ "$RESTART" = "1" ]; then
    say "Restart splunkd"
    run t_exec "$INDEXER_TARGET"   "$IDX_HOME/bin/splunk" restart --answer-yes
    if [ "$COLLECTOR_TARGET" != "$INDEXER_TARGET" ]; then
        run t_exec "$COLLECTOR_TARGET" "$COL_HOME/bin/splunk" restart --answer-yes
    fi
else
    say "Restart skipped (RESTART=0); inputs apply on the next restart"
fi

# -------------------------------------------------------------- verify

say "Verify"
if [ "$APPLY" = "1" ]; then
    t_exec "$INDEXER_TARGET" "$IDX_HOME/bin/splunk" btool check \
        > "$WORK/btool-check.after.txt" 2>&1 || true
    printf '  btool check: %s line(s) before, %s after\n' \
        "$(wc -l < "$WORK/btool-check.before.txt")" \
        "$(wc -l < "$WORK/btool-check.after.txt")"
    if ! diff -q "$WORK/btool-check.before.txt" "$WORK/btool-check.after.txt" >/dev/null; then
        echo "  --- new btool output, declare these ---"
        diff "$WORK/btool-check.before.txt" "$WORK/btool-check.after.txt" || true
    fi
    t_exec "$INDEXER_TARGET" "$IDX_HOME/bin/splunk" btool indexes list 2>/dev/null \
        | grep '^\[' | sort > "$WORK/indexes.after.txt" || true
    echo "  indexes added:"
    comm -13 <(sort "$WORK/indexes.before.txt") <(sort "$WORK/indexes.after.txt") | sed 's/^/    /'
    echo
    echo "  Changed:"
    echo "    indexer   $TA_NAME (parsing, inputs disabled), $INDEX_APP, index $INDEX_NAME"
    echo "    collector $TA_NAME (collection), $INPUTS_APP"
    [ "$RESTART" = "1" ] && echo "    splunkd restarted"
else
    echo "  dry run: nothing to verify"
fi

echo
echo "artifacts and baseline: $WORK"
