#!/bin/bash
set -euo pipefail

TARGET_DIR="${1:-/workspace/terraform}"
FAILED=0

export TF_PLUGIN_CACHE_DIR="${TF_PLUGIN_CACHE_DIR:-/tmp/tofu-plugin-cache}"
mkdir -p "$TF_PLUGIN_CACHE_DIR"

mapfile -t tf_dirs < <(find "$TARGET_DIR" -name "*.tf" -exec dirname {} \; | sort -u)

if [ "${#tf_dirs[@]}" -eq 0 ]; then
  echo "no .tf files found under ${TARGET_DIR}"
  exit 1
fi

echo "== tofu fmt -check (recursive) =="
if ! tofu fmt -check -diff -recursive "$TARGET_DIR"; then
  echo "tofu fmt found unformatted files"
  FAILED=1
fi

tflint --init >/dev/null 2>&1 || true

for dir in "${tf_dirs[@]}"; do
  echo "== ${dir} =="

  if ! (cd "$dir" && tofu init -backend=false -input=false >/tmp/tofu-init.log 2>&1); then
    echo "tofu init failed in ${dir}:"
    cat /tmp/tofu-init.log
    FAILED=1
    continue
  fi

  if ! (cd "$dir" && tofu validate); then
    echo "tofu validate failed in ${dir}"
    FAILED=1
  fi

  if ! (cd "$dir" && tflint); then
    echo "tflint found issues in ${dir}"
    FAILED=1
  fi
done

mapfile -t pkr_dirs < <(find "$TARGET_DIR" -name "*.pkr.hcl" -exec dirname {} \; | sort -u)
for dir in "${pkr_dirs[@]}"; do
  echo "== packer: ${dir} =="

  if ! packer fmt -check -diff "$dir"; then
    echo "packer fmt found unformatted files in ${dir}"
    FAILED=1
  fi

  if ! (cd "$dir" && packer init . >/tmp/packer-init.log 2>&1); then
    echo "packer init failed in ${dir}:"
    cat /tmp/packer-init.log
    FAILED=1
    continue
  fi

  if ! (cd "$dir" && packer validate .); then
    echo "packer validate failed in ${dir}"
    FAILED=1
  fi
done

exit "$FAILED"
