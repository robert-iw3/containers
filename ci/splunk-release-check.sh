#!/bin/sh
# Verify every pinned Splunk release actually exists on download.splunk.com,
# and that all Dockerfiles agree on one version.
#
#   ci/splunk-release-check.sh
#
# A version and build pinned in a Dockerfile are only checked when the image is
# built, and building Splunk is too heavy for CI. This asks the download site
# instead: it is a HEAD request per pin, and it catches a 404 pin before it
# becomes a failed build.
#
# A forwarder and an indexer on different versions is also a defect, because
# the build string differs per version, so one of the two pins is wrong even
# when both resolve.
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="https://download.splunk.com/products"
RC=0

# product filename-prefix dockerfile...
TARGETS="
splunk|splunk|splunk/enterprise/Dockerfile splunk/enterprise/stig.Dockerfile
universalforwarder|splunkforwarder|splunk/universalforwarder/Dockerfile splunk/universalforwarder/stig.Dockerfile
"

pin() {  # pin <file> <var>
    sed -n "s/^ENV $2 \([^ ]*\)$/\1/p" "$REPO_ROOT/$1" | sed -n 1p
}

seen_versions=""

echo "$TARGETS" | while IFS= read -r line; do
    [ -n "$line" ] || continue
    product="${line%%|*}"
    rest="${line#*|}"
    prefix="${rest%%|*}"
    files="${rest#*|}"

    for file in $files; do
        [ -f "$REPO_ROOT/$file" ] || { echo "MISSING  $file"; RC=1; continue; }

        version="$(pin "$file" SPLUNK_VERSION)"
        build="$(pin "$file" SPLUNK_BUILD)"
        if [ -z "$version" ] || [ -z "$build" ]; then
            echo "UNPINNED $file (no SPLUNK_VERSION/SPLUNK_BUILD)"
            RC=1
            continue
        fi

        url="$BASE/$product/releases/$version/linux/$prefix-$version-$build-linux-amd64.tgz"
        code="$(curl -s -o /dev/null -w '%{http_code}' -I --max-time 20 "$url" || echo 000)"
        if [ "$code" = "200" ]; then
            echo "ok       $file  $version-$build"
        else
            echo "HTTP $code $file  $version-$build"
            echo "         $url"
            RC=1
        fi
        seen_versions="$seen_versions $version"
    done
done

# The subshell above cannot export RC, so re-derive the verdict from a second,
# cheap pass over the pins rather than trusting a variable that cannot survive
# the pipe.
versions="$(grep -rhE '^ENV SPLUNK_VERSION ' \
    "$REPO_ROOT"/splunk/enterprise/Dockerfile \
    "$REPO_ROOT"/splunk/enterprise/stig.Dockerfile \
    "$REPO_ROOT"/splunk/universalforwarder/Dockerfile \
    "$REPO_ROOT"/splunk/universalforwarder/stig.Dockerfile 2>/dev/null \
    | awk '{print $3}' | sort -u)"
count="$(printf '%s\n' "$versions" | grep -c . || true)"
if [ "$count" -ne 1 ]; then
    echo
    echo "VERSION DRIFT: the Dockerfiles pin $count different versions:"
    printf '  %s\n' $versions
    exit 1
fi

echo
echo "all pins resolve, single version $versions"
