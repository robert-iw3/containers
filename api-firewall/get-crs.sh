#!/bin/sh
# Download the OWASP Core Rule Set into ./crs for the Coraza WAF layer.
# https://github.com/coreruleset/coreruleset
#
# After running, enable the WAF in .env:
#   APIFW_MODSEC_CONF_FILES=/opt/resources/config/coraza.conf;/opt/resources/crs/crs-setup.conf
#   APIFW_MODSEC_RULES_DIR=/opt/resources/crs/rules
set -eu

cd "$(dirname "$0")"

CRS_VERSION="${CRS_VERSION:-4.28.0}"
CRS_URL="https://github.com/coreruleset/coreruleset/archive/refs/tags/v${CRS_VERSION}.tar.gz"
CRS_DIR=crs

if [ -f "$CRS_DIR/crs-setup.conf" ] && [ "${1:-}" != "-f" ]; then
    echo "CRS already present in $CRS_DIR/ (use -f to re-download)" >&2
    exit 1
fi

echo "--> Downloading OWASP CRS v${CRS_VERSION}..."
rm -rf "$CRS_DIR"
mkdir -p "$CRS_DIR"
touch "$CRS_DIR/.gitkeep"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$CRS_URL" -o "$tmp/crs.tar.gz"
else
    wget -q "$CRS_URL" -O "$tmp/crs.tar.gz"
fi

tar -xzf "$tmp/crs.tar.gz" --strip-components 1 -C "$CRS_DIR"
# Activate the default setup shipped by upstream.
cp "$CRS_DIR/crs-setup.conf.example" "$CRS_DIR/crs-setup.conf"

echo "--> CRS v${CRS_VERSION} installed in $CRS_DIR/."
echo "    Enable it via APIFW_MODSEC_* in .env (see .env.example)."
