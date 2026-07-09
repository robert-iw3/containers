#!/bin/bash

# Check if Dockerfile path is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <path_to_dockerfile>"
    exit 1
fi

DOCKERFILE="$1"

# Fetch latest versions (strip 'v' prefix from tags)
SYFT_VER=$(curl -s https://api.github.com/repos/anchore/syft/releases/latest | jq -r .tag_name | sed 's/^v//')
GRYPE_VER=$(curl -s https://api.github.com/repos/anchore/grype/releases/latest | jq -r .tag_name | sed 's/^v//')

echo "Updating Syft to version: $SYFT_VER"
echo "Updating Grype to version: $GRYPE_VER"

# Update environment variables
sed -i.bak "s/^ENV SYFT_VER=[^ ]*/ENV SYFT_VER=${SYFT_VER}/" "$DOCKERFILE"
sed -i.bak "s/^ENV GRYPE_VER=[^ ]*/ENV GRYPE_VER=${GRYPE_VER}/" "$DOCKERFILE"

# Update the label (schema-version field)
sed -i.bak "s/schema-version='Grype [^,]*,\s*Syft [^']*'/schema-version='Grype ${GRYPE_VER}, Syft ${SYFT_VER}'/" "$DOCKERFILE"

# Clean up backup
rm -f "${DOCKERFILE}.bak"

echo "Dockerfile updated successfully."