#!/bin/sh
# Verify the pinned Cribl release exists and that every file agrees on it.
#
#   ci/cribl-release-check.sh
#
# The Dockerfile pins a version AND a build string; the compose files pin an
# image tag. A tag that resolves while the tarball 404s still breaks the build,
# and two files on different versions means one of them is wrong even when both
# resolve. This asks the CDN and the registry rather than waiting for a build.
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CRIBL="${REPO_ROOT}/cribl"
RC=0

version="$(sed -n 's/.*cribl_version="\([^"]*\)".*/\1/p' "${CRIBL}/Dockerfile" | sed -n 1p)"
build="$(sed -n 's/.*cribl_build="\([^"]*\)".*/\1/p' "${CRIBL}/Dockerfile" | sed -n 1p)"

if [ -z "$version" ] || [ -z "$build" ]; then
    echo "UNPINNED cribl/Dockerfile has no cribl_version/cribl_build"
    exit 1
fi

url="https://cdn.cribl.io/dl/${version}/cribl-${version}-${build}-linux-x64.tgz"
code="$(curl -s -o /dev/null -w '%{http_code}' -I --max-time 20 "$url" || echo 000)"
if [ "$code" = "200" ]; then
    echo "ok       tarball ${version}-${build}"
else
    echo "HTTP $code tarball ${version}-${build}"
    echo "         $url"
    RC=1
fi

code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
    "https://hub.docker.com/v2/repositories/cribl/cribl/tags/${version}" || echo 000)"
if [ "$code" = "200" ]; then
    echo "ok       image tag cribl/cribl:${version}"
else
    echo "HTTP $code image tag cribl/cribl:${version}"
    RC=1
fi

# Every tag referenced anywhere under cribl/ must be the pinned version.
tags="$(grep -rhoE 'cribl/cribl:[0-9]+\.[0-9]+\.[0-9]+' "$CRIBL" 2>/dev/null \
    | sed 's/.*://' | sort -u)"
count="$(printf '%s\n' "$tags" | grep -c . || true)"
if [ "$count" -gt 1 ]; then
    echo
    echo "VERSION DRIFT: files under cribl/ reference $count versions:"
    printf '  %s\n' $tags
    RC=1
elif [ -n "$tags" ] && [ "$tags" != "$version" ]; then
    echo
    echo "VERSION DRIFT: Dockerfile pins ${version}, compose/k8s reference ${tags}"
    RC=1
fi

[ "$RC" = 0 ] && echo "" && echo "all cribl pins resolve, single version ${version}"
exit $RC
