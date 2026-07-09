#!/usr/bin/env bash

set -e
set -o pipefail

DOCKER_IMAGE="$(grep -Ev '(^#|^\s*$|^\s*\t*#)' DockerImage.txt)"
NIFI_IMAGE_VERSION="$(echo "${DOCKER_IMAGE}" | cut -d : -f 2)"

echo "Running Docker Image: ${DOCKER_IMAGE}"
docker run -d --name "nifi-${NIFI_IMAGE_VERSION}" -p 8443:8443 -p 10000:10000 -p 8000:8000 "${DOCKER_IMAGE}"
