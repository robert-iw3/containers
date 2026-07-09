#!/usr/bin/env bash

set -e
set -o pipefail

DOCKER_UID="${1:-1000}"
DOCKER_GID="${2:-1000}"
MIRROR="${3:-https://archive.apache.org/dist}"
BASE="${4:-${MIRROR}}"
DISTRO_PATH="${5:-}"

DOCKER_IMAGE="$(grep -Ev '(^#|^\s*$|^\s*\t*#)' DockerImage.txt)"
NIFI_IMAGE_VERSION="$(echo "${DOCKER_IMAGE}" | cut -d : -f 2)"
if [ -z "${DISTRO_PATH}" ]; then
  DISTRO_PATH="${NIFI_IMAGE_VERSION}"
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
root_dir="$(dirname "$(dirname "${script_dir}")")"
mvn_cmd=("${root_dir}/mvnw" -f "${root_dir}/pom.xml" help:evaluate -q -D forceStdout)
IMAGE_NAME="$("${mvn_cmd[@]}" -D expression=docker.jdk.image.name)"
IMAGE_TAG="$("${mvn_cmd[@]}" -D expression=docker.image.tag)"

echo "Building NiFi Image: '${DOCKER_IMAGE}' Version: '${NIFI_IMAGE_VERSION}' Using: '${IMAGE_NAME}:${IMAGE_TAG}' Mirror: '${MIRROR}' Base: '${BASE} Path: '${DISTRO_PATH}' User/Group: '${DOCKER_UID}/${DOCKER_GID}'"
docker build --build-arg IMAGE_NAME="${IMAGE_NAME}" --build-arg IMAGE_TAG="${IMAGE_TAG}" --build-arg UID="${DOCKER_UID}" --build-arg GID="${DOCKER_GID}" --build-arg NIFI_VERSION="${NIFI_IMAGE_VERSION}" --build-arg MIRROR_BASE_URL="${MIRROR}" --build-arg BASE_URL="${BASE}" --build-arg DISTRO_PATH="${DISTRO_PATH}" -t "${DOCKER_IMAGE}" .
