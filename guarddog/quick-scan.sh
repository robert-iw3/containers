#!/usr/bin/env bash
# example for vscode extensions
set -e

IMAGE_NAME="local/guarddog-scanner:latest"
CONTAINER_NAME="guarddog-scan-runner"
EXTENSION_ID="DaltonMenezes.aura-theme"
OUTPUT_FILE="guarddog_scan_results.txt"

echo "=== [1/4] Building GuardDog Image ==="
podman build -t "$IMAGE_NAME" .

echo "=== [2/4] Starting Temporary Container ==="
podman run -d --name "$CONTAINER_NAME" "$IMAGE_NAME"

trap 'echo "=== Cleaning up container... ==="; podman rm -f "$CONTAINER_NAME" >/dev/null 2>&1' EXIT

echo "=== [3/4] Running GuardDog Scan on $EXTENSION_ID ==="
docker exec "$CONTAINER_NAME" /venv/bin/guarddog extension scan "$EXTENSION_ID" > "$OUTPUT_FILE" 2>&1 || true

echo "=== [4/4] Scan Complete ==="
echo "Results successfully saved to: $(pwd)/$OUTPUT_FILE"
echo "--------------------------------------------------"
cat "$OUTPUT_FILE"
echo "--------------------------------------------------"

