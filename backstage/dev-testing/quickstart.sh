#!/bin/bash

# using ubuntu jammy

apt-get install -y \
    yarn \
    npm \
    git \
    make \
    build-essential \
    curl \
    wget \
    podman \
    python3 \
    g++

git clone https://github.com/backstage/backstage.git
cd backstage

host-prep()
{
    yarn install --frozen-lockfile
    # tsc outputs type definitions to dist-types/ in the repo root, which are then consumed by the build
    yarn tsc
    # Build the backend, which bundles it all up into the packages/backend/dist folder.
    # The configuration files here should match the one you use inside the Dockerfile below.
    yarn build:backend --config ../../app-config.yaml
}

podman-build-run()
{
    cp ../Dockerfile .
    podman build -t backstage .
    podman run --rm -it --name backstage -p 7007:7007 backstage
}

tee .dockerignore <<EOF
dist-types
node_modules
packages/*/dist
packages/*/node_modules
plugins/*/dist
plugins/*/node_modules
EOF

echo "backstage" | npx --yes @backstage/create-app@latest
yarn dev
host-prep
podman-build-run