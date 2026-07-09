#!/usr/bin/env bash

set -euo pipefail

DOCKERFILE="${1:-Dockerfile}"
BACKUP="${DOCKERFILE}.bak"

if [[ ! -f "$DOCKERFILE" ]]; then
    echo "Error: $DOCKERFILE not found!"
    echo "Usage: $0 [path/to/Dockerfile]"
    exit 1
fi

echo "Fetching latest Arkime release from github.com/arkime/arkime ..."

LATEST_TAG=$(curl -s https://api.github.com/repos/arkime/arkime/releases/latest \
             | jq -r '.tag_name')

# Strip leading 'v'
ARKIME_VERSION="${LATEST_TAG#v}"
DEB_PACKAGE="arkime_${ARKIME_VERSION}-1.debian12_amd64.deb"

echo "Latest Arkime version: $ARKIME_VERSION"
echo "DEB package: $DEB_PACKAGE"

echo "Backing up $DOCKERFILE → $BACKUP"
cp "$DOCKERFILE" "$BACKUP"

echo "Patching $DOCKERFILE ..."
sed -i \
    -e "s|ARG ARKIME_VERSION=[0-9][0-9.]*|ARG ARKIME_VERSION=${ARKIME_VERSION}|g" \
    -e "s|ARG ARKIME_DEB_PACKAGE=\"arkime_[^\"]*\"|ARG ARKIME_DEB_PACKAGE=\"${DEB_PACKAGE}\"|g" \
    -e "s|curl -L -O \".*arkime_.*debian12_amd64\.deb\"|curl -L -O \"https://github.com/arkime/arkime/releases/download/${LATEST_TAG}/${DEB_PACKAGE}\"|" \
    "$DOCKERFILE"

echo "Done! Dockerfile now uses Arkime v${ARKIME_VERSION}"
echo "   Backup saved as $BACKUP"
echo ""
echo "Test it:"
echo "   docker build --no-cache -t arkime:test ."