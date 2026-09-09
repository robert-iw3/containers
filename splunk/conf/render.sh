#!/usr/bin/env bash
# Render the hardened Splunk configuration for a real deployment.
#
#   ./render.sh <out-dir> [--certs DIR] [--server-name NAME]
#               [--accept-from CIDR] [--web-port PORT] [--allowed-domains LIST]
#               [--fqdn URL] [--forwarding]
#
# The files in this directory are TEMPLATES, not deployable config: they carry
# placeholders (<private-password-of-splunk-cert.key>, splunkhostname,
# 123.123.123.0/24) and reference certificates and branding images that do not
# exist. That is why nothing has ever mounted them, and why a running instance
# has none of these 88 settings - including enableSplunkWebSSL and the
# allowedDomainList whose absence Splunk warns about at startup.
#
# This renders them into a directory you mount at
# $SPLUNK_HOME/etc/system/local. Generate the certificates first; see --certs.
#
# Three files are deliberately NOT rendered into system/local:
#
#   user-seed.conf     its HASHED_PASSWORD placeholder fights the password the
#                      entrypoint seeds on first start.
#   splunk-launch.conf belongs at $SPLUNK_HOME/etc, not system/local, where it
#                      is read by nothing.
#   outputs.conf       [indexAndForward] selectiveIndexing = true sends every
#                      event to a tcpout group and indexes only what is
#                      explicitly routed. On an indexer that is a total data
#                      loss: HEC still answers 200, index_thruput stays at 0
#                      events, and even _internal is empty. Pass --forwarding
#                      on an instance that really does forward to indexers.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:?usage: render.sh <out-dir> [options]}"; shift || true

CERTS="/opt/splunk/etc/auth/mycerts"
SERVER_NAME="splunk"
ACCEPT_FROM="127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
WEB_PORT="8000"
ALLOWED_DOMAINS=""
FQDN=""
FORWARDING=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --certs)           CERTS="$2"; shift 2 ;;
        --server-name)     SERVER_NAME="$2"; shift 2 ;;
        --accept-from)     ACCEPT_FROM="$2"; shift 2 ;;
        --web-port)        WEB_PORT="$2"; shift 2 ;;
        --allowed-domains) ALLOWED_DOMAINS="$2"; shift 2 ;;
        # SAML is opt-in. authentication.conf sets authType = SAML against a
        # placeholder IdP; deploying that as-is makes login impossible, so
        # without --fqdn the SAML settings are dropped and password auth with
        # minPasswordLength is kept.
        --fqdn)            FQDN="$2"; shift 2 ;;
        # Only for an instance that forwards to indexers. See the header.
        --forwarding)      FORWARDING=1; shift ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

mkdir -p "$OUT"
rendered=0
skipped_outputs=0

# Remove a previous render of anything this run will not emit. Without this a
# directory rendered by an older copy of this script keeps its outputs.conf,
# and whoever mounts it gets the setting this script now refuses to write.
for name in user-seed.conf splunk-launch.conf; do
    rm -f "$OUT/$name"
done

for src in "$HERE"/*.conf; do
    name="$(basename "$src")"
    # Seeded by the entrypoint on first start; a placeholder hash here makes
    # the admin account unusable.
    [[ "$name" == "user-seed.conf" ]] && continue
    # Read only from $SPLUNK_HOME/etc; in system/local it does nothing.
    [[ "$name" == "splunk-launch.conf" ]] && continue
    # selectiveIndexing on an indexer discards everything. See the header.
    if [[ "$name" == "outputs.conf" && "$FORWARDING" != "1" ]]; then
        rm -f "$OUT/$name"
        skipped_outputs=1
        continue
    fi

    sed \
        -e "s|/opt/splunk/etc/auth/mycerts|${CERTS}|g" \
        -e "s|^serverName = splunkhostname|serverName = ${SERVER_NAME}|" \
        -e "s|^acceptFrom = .*|acceptFrom = ${ACCEPT_FROM}|" \
        -e "s|^httpport = 443|httpport = ${WEB_PORT}|" \
        "$src" > "$OUT/$name"

    # An sslPassword line with the placeholder makes Splunk refuse the key.
    # Keys generated unencrypted need no password at all, so drop the line
    # rather than substitute a fake one.
    sed -i '/^sslPassword = <private-password/d' "$OUT/$name"

    # Branding references point at images that are not in this repo; Splunk
    # logs an error for each missing asset on every page load.
    sed -i '/^customFavicon\|^loginCustomLogo\|^loginBackgroundImageOption\|^loginCustomBackgroundImage/d' "$OUT/$name"

    if [[ "$name" == "authentication.conf" ]]; then
        if [[ -n "$FQDN" ]]; then
            sed -i "s|https://splunkhostname|${FQDN}|g" "$OUT/$name"
        else
            # Keep [splunk_auth] (minPasswordLength); drop the SAML stanzas and
            # the authType/authSettings that select them.
            python3 - "$OUT/$name" <<'PYIN'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); out, skip = [], False
for line in p.read_text().splitlines():
    s = line.strip()
    if s.startswith("["):
        skip = s in ("[AAD]", "[authenticationResponseAttrMap_SAML]", "[roleMap_SAML]")
    if skip:
        continue
    if s.startswith("authType") or s.startswith("authSettings"):
        continue
    out.append(line)
out.insert(0, "# SAML dropped at render time: no --fqdn was given, and the")
out.insert(1, "# shipped stanza points at a placeholder IdP. Password auth with")
out.insert(2, "# minPasswordLength applies instead.")
p.write_text("\n".join(out) + "\n")
PYIN
        fi
    fi

    if [[ -n "$ALLOWED_DOMAINS" ]]; then
        sed -i "s|^allowedDomainList = .*|allowedDomainList = ${ALLOWED_DOMAINS}|" "$OUT/$name"
    fi
    rendered=$((rendered + 1))
done

# Nothing rendered may still contain a placeholder: a config that looks applied
# and is refused at load is worse than one that was never mounted.
if grep -rnE "<[a-z-]+>|splunkhostname|123\.123\.123" "$OUT" | grep -v "^.*:#" ; then
    echo "render.sh: placeholders survived rendering (above)" >&2
    exit 1
fi

if [[ "$skipped_outputs" == "1" ]]; then
    echo "render.sh: outputs.conf skipped (selectiveIndexing discards every event on an indexer; --forwarding to include it)"
fi
echo "render.sh: splunk-launch.conf skipped (its destination is \$SPLUNK_HOME/etc, not system/local)"
echo "render.sh: ${rendered} files -> ${OUT}"
grep -hE "^(enableSplunkWebSSL|enableSplunkdSSL|requireClientCert|minPasswordLength|allowedDomainList|httpport)" "$OUT"/*.conf | sed 's/^/  /'
