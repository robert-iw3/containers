#!/usr/bin/env bash
# Pack the images into images/*.tar.gz so deploying needs NO network: run this at
# home after ./uat.sh passes, then copy the whole secure_browser/ directory. At the
# hotel, run.sh loads the tarballs instead of pulling or building anything.
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p images
for pair in "localhost/secure-browser:." "localhost/secure-browser-broker:broker/"; do
    img=${pair%%:*}
    ctx=${pair#*:}
    podman image exists "$img" || podman build -t "$img" "$ctx"
    out="images/$(basename "$img").tar.gz"
    echo "[pack] ${img} -> ${out}"
    podman save "$img" | gzip -1 > "$out"
done
ls -lh images/
echo "[pack] done — copy the whole secure_browser/ directory to travel with it"
