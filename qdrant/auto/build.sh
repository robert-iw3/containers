#!/usr/bin/env bash
#debian

set -e

add-apt-repository --component contrib non-free
apt-get update -y

apt-get install -y \
    linux-headers-$(uname -r) \
    podman \
    wget \
    unzip \
    nvidia-driver

wget https://github.com/qdrant/qdrant/archive/refs/heads/master.zip
unzip master.zip

cd qdrant-master/

podman build -t qdrant .
podman run --rm -it --name qdrant -p 6333:6333 -d qdrant
