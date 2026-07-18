#!/usr/bin/env bash
# Validate every terraform root using the containerized terraform CLI.
# Builds the image on first run; providers are cached in the tf-plugin-cache
# volume so re-runs are fast.
#
#   ./scripts/validate.sh            # fmt-check + validate all roots
#   ./scripts/validate.sh aws        # a single root
set -euo pipefail

cd "$(dirname "$0")/.."

RUNTIME="${RUNTIME:-podman}"
IMAGE="${IMAGE:-localhost/terraform:1.15.8}"
ROOTS=("${@:-aws azure gcp vmware}")
[ $# -eq 0 ] && ROOTS=(aws azure gcp vmware)

if ! "$RUNTIME" image exists "$IMAGE" 2>/dev/null; then
  echo "==> building $IMAGE"
  "$RUNTIME" build -t "$IMAGE" .
fi

tf() {
  local root=$1; shift
  "$RUNTIME" run --rm \
    -v "$(pwd)":/workspace:z \
    -v tf-plugin-cache:/tfcache \
    -w "/workspace/$root" \
    "$IMAGE" "$@"
}

rc=0
for root in "${ROOTS[@]}"; do
  echo "==> $root: fmt -check"
  tf "$root" fmt -check -diff || rc=1
  echo "==> $root: init"
  tf "$root" init -backend=false -input=false -upgrade >/dev/null
  echo "==> $root: validate"
  tf "$root" validate || rc=1
done

exit $rc
