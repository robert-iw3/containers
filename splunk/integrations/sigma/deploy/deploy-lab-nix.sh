#!/usr/bin/env bash
# Install Splunk_TA_nix into the epo-uat lab and start ingesting this host's
# real Linux audit data, so Sigma rules can be tested against actual events
# rather than against assumptions about the schema.
#
# Split of responsibilities, which is how a real deployment does it:
#   epo-uat-uf        collection: the TA plus monitor inputs
#   epo-uat-indexer   parsing: the TA (props/transforms/lookups) and the index
#
# Two things reading the TA made necessary, and which a naive install misses:
#
#   1. Splunk_TA_nix never assigns the linux_audit sourcetype. It ships no
#      source:: stanza for it and never mentions audit.log, so the sourcetype
#      has to be set explicitly on the monitor stanza.
#   2. The TA's own "auditd" sourcetype comes from rlog.sh piping ausearch -i,
#      whose interpreted output resolves uid to a name and does not carry the
#      raw a0/a1 argument fields. Sigma's auditd rules match the raw format,
#      so this deploys a file monitor on audit.log as linux_audit and leaves
#      the scripted input off.
#
# The lab containers have no bind mount for the host's /var/log, so real log
# content is staged into a directory inside the forwarder. The events are the
# host's genuine records; only the transport is a copy.
#
# Idempotent: re-running replaces staged config and re-syncs the log data.
# Nothing is written to etc/system/local and nothing under splunk/hardening
# is touched.
set -euo pipefail

TA_SPL="${TA_SPL:-$HOME/Downloads/splunk-add-on-for-unix-and-linux_1034.spl}"
TA_SHA256="${TA_SHA256:-9bfb2061b55961841d5babba04ead35509730dc73a7b6bfbc676a7216e7f1ca2}"
INDEXER="${INDEXER:-epo-uat-indexer}"
UF="${UF:-epo-uat-uf}"
# Each container runs splunkd as its own account, and the CLI chowns all of
# SPLUNK_HOME to whoever invokes it. Running the forwarder CLI as splunk
# rewrites ownership out from under the ansible-owned var/ directory, after
# which splunkd cannot write its pid file and will not start.
INDEXER_USER="${INDEXER_USER:-splunk}"
UF_USER="${UF_USER:-$(podman inspect "${UF:-epo-uat-uf}" --format '{{.Config.User}}' 2>/dev/null)}"
UF_USER="${UF_USER:-splunk}"
INDEX_NAME="${INDEX_NAME:-linux_lab}"
# Staged under the app rather than var/: on this image var/ is owned by
# another account, and keeping the data inside the app means removing
# the app removes the data.
STAGE_DIR="${STAGE_DIR:-/opt/splunkforwarder/etc/apps/sigma_lab_inputs/lab-logs}"
WORK="${WORK:-$(mktemp -d)}"
APPLY="${APPLY:-0}"

say()  { printf '\n== %s\n' "$*"; }
run()  {
    if [ "$APPLY" = "1" ]; then "$@"; else printf '  [dry-run] %s\n' "$*"; fi
}

if [ "$APPLY" != "1" ]; then
    echo "DRY RUN. Nothing will change. Re-run with APPLY=1 to deploy."
fi

# ----------------------------------------------------------- preflight

say "Preflight"
for c in "$INDEXER" "$UF"; do
    if ! podman container exists "$c"; then
        echo "FAIL: container $c does not exist" >&2; exit 1
    fi
    printf '  %s: %s\n' "$c" "$(podman ps --filter "name=^${c}$" --format '{{.Status}}')"
done
printf '  service accounts: %s=%s  %s=%s\n' \
    "$INDEXER" "$INDEXER_USER" "$UF" "$UF_USER"

if [ ! -f "$TA_SPL" ]; then
    echo "FAIL: add-on package not found: $TA_SPL" >&2
    echo "      Download Splunk_TA_nix (Splunkbase app 833) and set TA_SPL." >&2
    exit 1
fi

actual=$(sha256sum "$TA_SPL" | cut -d' ' -f1)
if [ "$actual" != "$TA_SHA256" ]; then
    echo "FAIL: checksum mismatch for $TA_SPL" >&2
    echo "      expected $TA_SHA256" >&2
    echo "      actual   $actual" >&2
    exit 1
fi
printf '  package: %s\n  sha256 verified\n' "$(basename "$TA_SPL")"

# Refuse to unpack an archive that writes outside its own directory.
if tar -tzf "$TA_SPL" | grep -qE '^/|\.\.'; then
    echo "FAIL: archive contains absolute or parent paths" >&2; exit 1
fi

say "Baseline (record this: the assessment effort re-runs against the result)"
podman exec -u "$INDEXER_USER" "$INDEXER" /opt/splunk/bin/splunk btool check \
    > "$WORK/btool-check.before.txt" 2>&1 || true
printf '  indexer btool check: %s line(s)\n' "$(wc -l < "$WORK/btool-check.before.txt")"
podman exec -u "$INDEXER_USER" "$INDEXER" sh -c 'ls -1 /opt/splunk/etc/apps' \
    > "$WORK/apps-indexer.before.txt"
podman exec -u "$INDEXER_USER" "$INDEXER" /opt/splunk/bin/splunk btool indexes list 2>/dev/null \
    | grep '^\[' | sort > "$WORK/indexes.before.txt"
printf '  indexer apps: %s  indexes: %s\n' \
    "$(wc -l < "$WORK/apps-indexer.before.txt")" "$(wc -l < "$WORK/indexes.before.txt")"
echo "  baseline written to $WORK"

# ----------------------------------------------------------- unpack

say "Unpack the add-on"
mkdir -p "$WORK/ta"
tar -xzf "$TA_SPL" -C "$WORK/ta"
if [ ! -d "$WORK/ta/Splunk_TA_nix" ]; then
    echo "FAIL: expected Splunk_TA_nix/ in the archive" >&2; exit 1
fi
printf '  version: %s\n' "$(sed -n 1p "$WORK/ta/Splunk_TA_nix/VERSION" 2>/dev/null)"

# ----------------------------------------------------- indexer: parsing

say "Indexer: install the add-on for parsing"
run podman cp "$WORK/ta/Splunk_TA_nix" "$INDEXER:/opt/splunk/etc/apps/Splunk_TA_nix"
run podman exec -u root "$INDEXER" chown -R "$INDEXER_USER:$INDEXER_USER" /opt/splunk/etc/apps/Splunk_TA_nix

# The indexer parses; it must not run the add-on's scripted inputs.
say "Indexer: create the directories that follow"
# podman cp will not create a missing parent, so every destination
# directory is made before anything is copied into it.
run podman exec -u "$INDEXER_USER" "$INDEXER" mkdir -p \
    /opt/splunk/etc/apps/Splunk_TA_nix/local \
    /opt/splunk/etc/apps/sigma_lab_indexes/local \
    /opt/splunk/etc/apps/sigma_lab_indexes/metadata

say "Indexer: disable every input the add-on ships"
cat > "$WORK/indexer-inputs.conf" <<'CONF'
# The indexer uses this add-on for parsing only. Every input it ships is
# disabled here so the indexer does not start collecting from itself.
[default]
disabled = 1
CONF
run podman cp "$WORK/indexer-inputs.conf" \
    "$INDEXER:/opt/splunk/etc/apps/Splunk_TA_nix/local/inputs.conf"

say "Indexer: create index $INDEX_NAME"
cat > "$WORK/indexes.conf" <<CONF
# Linux audit data for the Sigma detection integration.
[$INDEX_NAME]
homePath   = \$SPLUNK_DB/$INDEX_NAME/db
coldPath   = \$SPLUNK_DB/$INDEX_NAME/colddb
thawedPath = \$SPLUNK_DB/$INDEX_NAME/thaweddb
maxTotalDataSizeMB = 4096
frozenTimePeriodInSecs = 2592000
CONF
cat > "$WORK/index-app.conf" <<'CONF'
[install]
state = enabled

[ui]
is_visible = 0
label = Sigma Lab Indexes
CONF
cat > "$WORK/index-local.meta" <<'META'
[]
access = read : [ * ], write : [ admin ]
export = system
META
run podman cp "$WORK/indexes.conf"     "$INDEXER:/opt/splunk/etc/apps/sigma_lab_indexes/local/indexes.conf"
run podman cp "$WORK/index-app.conf"   "$INDEXER:/opt/splunk/etc/apps/sigma_lab_indexes/local/app.conf"
run podman cp "$WORK/index-local.meta" "$INDEXER:/opt/splunk/etc/apps/sigma_lab_indexes/metadata/local.meta"
run podman exec -u root "$INDEXER" chown -R "$INDEXER_USER:$INDEXER_USER" \
    /opt/splunk/etc/apps/sigma_lab_indexes /opt/splunk/etc/apps/Splunk_TA_nix

# -------------------------------------------------- forwarder: collection

say "Forwarder: install the add-on for collection"
run podman cp "$WORK/ta/Splunk_TA_nix" "$UF:/opt/splunkforwarder/etc/apps/Splunk_TA_nix"
run podman exec -u root "$UF" chown -R "$UF_USER:$UF_USER" /opt/splunkforwarder/etc/apps/Splunk_TA_nix

say "Forwarder: stage this host's real log data under $STAGE_DIR"
run podman exec -u "$UF_USER" "$UF" mkdir -p \
    /opt/splunkforwarder/etc/apps/sigma_lab_inputs/local "$STAGE_DIR"

staged=0
# audit.log is the source Sigma's auditd rules read. It is root:adm 0640, so
# this only works where the running user can read it.
for src in /var/log/audit/audit.log /var/log/auth.log /var/log/syslog; do
    if [ -r "$src" ]; then
        dest="$STAGE_DIR/$(basename "$src")"
        printf '  staging %s -> %s (%s bytes)\n' "$src" "$dest" "$(stat -c%s "$src")"
        run podman cp "$src" "$UF:$dest"
        staged=$((staged+1))
    else
        printf '  SKIP %s (not readable by %s)\n' "$src" "$(id -un)"
    fi
done
if [ "$staged" -eq 0 ]; then
    echo "FAIL: no host log readable; nothing to ingest" >&2; exit 1
fi
run podman exec -u root "$UF" chown -R "$UF_USER:$UF_USER" "$STAGE_DIR"

say "Forwarder: monitor inputs"
# sourcetype is explicit on every stanza. The add-on assigns linux_secure by
# source:: but has nothing at all for linux_audit, so leaving it to
# autodetection gets the wrong sourcetype and none of the CIM work runs.
cat > "$WORK/uf-inputs.conf" <<CONF
# Collection for the Sigma detection integration. Staged copies of this
# host's real Linux audit data; the lab containers do not mount /var/log.
#
# crcSalt makes each path distinct to the fishbucket, so restaging a file
# re-reads it instead of being treated as already seen.

[monitor://$STAGE_DIR/audit.log]
sourcetype = linux_audit
index = $INDEX_NAME
disabled = 0
crcSalt = <SOURCE>

[monitor://$STAGE_DIR/auth.log]
sourcetype = linux_secure
index = $INDEX_NAME
disabled = 0
crcSalt = <SOURCE>

[monitor://$STAGE_DIR/syslog]
sourcetype = syslog
index = $INDEX_NAME
disabled = 0
crcSalt = <SOURCE>
CONF
cat > "$WORK/uf-app.conf" <<'CONF'
[install]
state = enabled

[ui]
is_visible = 0
label = Sigma Lab Linux Inputs
CONF
run podman exec -u "$UF_USER" "$UF" mkdir -p \
    /opt/splunkforwarder/etc/apps/sigma_lab_inputs/local
run podman exec -u "$UF_USER" "$UF" mkdir -p \
    /opt/splunkforwarder/etc/apps/sigma_lab_inputs/local
run podman cp "$WORK/uf-inputs.conf" \
    "$UF:/opt/splunkforwarder/etc/apps/sigma_lab_inputs/local/inputs.conf"
run podman cp "$WORK/uf-app.conf" \
    "$UF:/opt/splunkforwarder/etc/apps/sigma_lab_inputs/local/app.conf"
run podman exec -u root "$UF" chown -R "$UF_USER:$UF_USER" \
    /opt/splunkforwarder/etc/apps/sigma_lab_inputs

# ----------------------------------------------------------- restart

say "Restart splunkd"
# The indexer needs a restart for a new index and new parsing config. The
# forwarder needs one to pick up a new app's inputs.
run podman exec -u "$INDEXER_USER" "$INDEXER" /opt/splunk/bin/splunk restart --answer-yes
run podman exec -u "$UF_USER" "$UF" /opt/splunkforwarder/bin/splunk restart --answer-yes

# ----------------------------------------------------------- verify

say "Verify"
if [ "$APPLY" = "1" ]; then
    podman exec -u "$INDEXER_USER" "$INDEXER" /opt/splunk/bin/splunk btool check \
        > "$WORK/btool-check.after.txt" 2>&1 || true
    before=$(wc -l < "$WORK/btool-check.before.txt")
    after=$(wc -l < "$WORK/btool-check.after.txt")
    printf '  btool check: %s line(s) before, %s after\n' "$before" "$after"
    if ! diff -q "$WORK/btool-check.before.txt" "$WORK/btool-check.after.txt" >/dev/null; then
        echo "  --- new btool output (declare these, they are not failures) ---"
        diff "$WORK/btool-check.before.txt" "$WORK/btool-check.after.txt" || true
    fi
    podman exec -u "$INDEXER_USER" "$INDEXER" /opt/splunk/bin/splunk btool indexes list 2>/dev/null \
        | grep '^\[' | sort > "$WORK/indexes.after.txt"
    echo "  --- indexes added ---"
    comm -13 <(sort "$WORK/indexes.before.txt") <(sort "$WORK/indexes.after.txt") | sed 's/^/    /'
    echo
    echo "  Changes made:"
    echo "    $INDEXER  apps: Splunk_TA_nix (parsing), sigma_lab_indexes"
    echo "    $UF        apps: Splunk_TA_nix (collection), sigma_lab_inputs"
    echo "    index:     $INDEX_NAME"
    echo "    splunkd restarted on both"
    echo
    echo "  Data should land within a minute. Check with:"
    echo "    podman exec -u splunk $INDEXER /opt/splunk/bin/splunk search \\"
    echo "      'index=$INDEX_NAME | stats count by sourcetype' -preview false"
else
    echo "  dry run: nothing to verify"
fi

echo
echo "artifacts and baseline: $WORK"
