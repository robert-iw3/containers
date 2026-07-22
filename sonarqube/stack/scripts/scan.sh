#!/bin/sh
# Recursively scan one or more codebases with SonarScanner and submit the
# analyses to the SonarQube instance.
#
#   scan.sh [--recursive] [PATH ...]
#
# Paths come from the command line, or from scan.paths in stack.yaml when
# none are given. Each path is analysed as its own project; with --recursive
# every project root discovered beneath a path (a directory holding a build
# marker such as pom.xml, package.json, go.mod, Cargo.toml, build.gradle or
# sonar-project.properties) becomes its own project.
#
# Configuration (environment, or stack.yaml scan.*):
#   SONAR_HOST_URL   SonarQube base URL (e.g. https://sonarqube.example.com:8443)
#   SONAR_TOKEN      a user/project analysis token (squ_...)
#   SONAR_NETWORK    optional container network to join (for internal access)
#   SONAR_TRUSTSTORE optional PKCS12/JKS truststore for a private CA (TLS)
#   SCANNER_IMAGE    override the scanner image
#   RUNTIME          podman (default) or docker
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
STACK_DIR="$(cd "$HERE/.." && pwd)"
CONFIG="${STACK_CONFIG:-$STACK_DIR/stack.yaml}"

RUNTIME="${RUNTIME:-podman}"
SCANNER_IMAGE="${SCANNER_IMAGE:-docker.io/sonarsource/sonar-scanner-cli:12.1}"
RECURSIVE=0

# Minimal, dependency-free reader for a single scalar under scan: in the
# flat stack.yaml (key: value). Only used to fill unset settings.
yaml_scan() { # yaml_scan <key>
    [ -f "$CONFIG" ] || return 0
    awk -v k="$1" '
        /^scan:/ {inscan=1; next}
        /^[a-zA-Z]/ {inscan=0}
        inscan && $1 == k":" { $1=""; sub(/^[ \t]+/,""); print; exit }
    ' "$CONFIG"
}

PATHS=""
for a in "$@"; do
    case "$a" in
        --recursive|-r) RECURSIVE=1 ;;
        *) PATHS="$PATHS $a" ;;
    esac
done

: "${SONAR_HOST_URL:=$(yaml_scan server)}"
: "${SONAR_TOKEN:=$(yaml_scan token)}"
: "${SONAR_NETWORK:=$(yaml_scan network)}"

if [ -z "${SONAR_HOST_URL:-}" ] || [ -z "${SONAR_TOKEN:-}" ]; then
    echo "!! set SONAR_HOST_URL and SONAR_TOKEN (env or stack.yaml scan.*)" >&2
    exit 2
fi

# Paths: CLI args win; otherwise every scan.paths entry in stack.yaml.
if [ -z "$(printf '%s' "$PATHS" | tr -d ' ')" ] && [ -f "$CONFIG" ]; then
    PATHS="$(awk '
        /^scan:/ {inscan=1; next}
        /^[a-zA-Z]/ {inscan=0}
        inscan && /^[ \t]+paths:/ {inpaths=1; next}
        inscan && inpaths && /^[ \t]+-[ \t]*/ { sub(/^[ \t]+-[ \t]*/,""); print; next }
        inscan && inpaths && /^[ \t]+[a-zA-Z]/ {inpaths=0}
    ' "$CONFIG")"
fi
if [ -z "$(printf '%s' "$PATHS" | tr -d ' \n')" ]; then
    echo "!! no paths given and none in $CONFIG (scan.paths)" >&2
    exit 2
fi

is_project_root() {
    for m in pom.xml package.json go.mod Cargo.toml build.gradle build.gradle.kts \
             sonar-project.properties; do
        [ -e "$1/$m" ] && return 0
    done
    return 1
}

# Emit the list of project roots for a path.
project_roots() {
    _p="$1"
    if [ "$RECURSIVE" -eq 1 ]; then
        # Deepest-first is wrong for grouping; take each marker dir once,
        # skipping vendored trees.
        find "$_p" \( -name node_modules -o -name .git -o -name target \
                      -o -name vendor -o -name dist -o -name build \) -prune -o \
             \( -name pom.xml -o -name package.json -o -name go.mod \
                -o -name Cargo.toml -o -name build.gradle -o -name build.gradle.kts \
                -o -name sonar-project.properties \) -print 2>/dev/null \
            | sed 's#/[^/]*$##' | sort -u
    else
        printf '%s\n' "$_p"
    fi
}

scan_one() { # scan_one <dir>
    _dir="$(cd "$1" 2>/dev/null && pwd)" || { echo "  skip (missing): $1"; return 0; }
    _key="$(basename "$_dir" | tr -c 'A-Za-z0-9_.:-' '_')"
    echo "== scanning $_dir  (projectKey=$_key)"
    set -- run --rm \
        -e SONAR_HOST_URL="$SONAR_HOST_URL" \
        -e SONAR_TOKEN="$SONAR_TOKEN" \
        -e SONAR_SCANNER_OPTS="-Dsonar.projectKey=$_key -Dsonar.projectName=$_key -Dsonar.sources=." \
        -v "$_dir:/usr/src:ro,z"
    [ -n "${SONAR_NETWORK:-}" ] && set -- "$@" --network "$SONAR_NETWORK"
    if [ -n "${SONAR_TRUSTSTORE:-}" ]; then
        set -- "$@" -v "$SONAR_TRUSTSTORE:/tls/truststore.p12:ro,z" \
            -e SONAR_SCANNER_OPTS="-Dsonar.projectKey=$_key -Dsonar.projectName=$_key -Dsonar.sources=. -Djavax.net.ssl.trustStore=/tls/truststore.p12 -Djavax.net.ssl.trustStoreType=PKCS12"
    fi
    "$RUNTIME" "$@" "$SCANNER_IMAGE"
}

RC=0
for p in $PATHS; do
    [ -d "$p" ] || { echo "  skip (not a dir): $p"; continue; }
    project_roots "$p" | while IFS= read -r root; do
        [ -n "$root" ] && { scan_one "$root" || RC=1; }
    done
done
exit "$RC"
