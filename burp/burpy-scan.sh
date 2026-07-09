#!/bin/bash
set -euo pipefail

# Configuration
BURP_HOST="burp.domainname.io"
BURP_PORT="8080"
PORTSWIGGER_EMAIL_ADDRESS="your_portswigger_email"
PORTSWIGGER_PASSWORD="yo_pass"
BURP_APIKEY="someapikey"
MODE="https" # http or https
WEBPORT="443"
RESULT_DIR="$(pwd)/burp"
TARGETS=("google-gruyere.appspot.com" "testhtml5.vulnweb.com" "HackThisSite.org" "www.root-me.org")
APP_NAME=("google" "testhtml5" "hackthissite" "rootme")

# Create result directory
mkdir -p "${RESULT_DIR}"

# Install dependencies
dnf update -y && dnf install -y podman

# Build Burp Suite image
podman build -t burp-suite-pro \
    --build-arg PORTSWIGGER_EMAIL_ADDRESS="${PORTSWIGGER_EMAIL_ADDRESS}" \
    --build-arg PORTSWIGGER_PASSWORD="${PORTSWIGGER_PASSWORD}" .

# Create network (only if it doesn't exist)
podman network inspect burp >/dev/null 2>&1 || podman network create burp

# Run Burp Suite container
podman run -d --rm \
    -p 8080:8080 \
    -p 1337:1337 \
    --name burp-pro \
    -e BURP_KEY="${BURP_APIKEY}" \
    -v "${RESULT_DIR}:/home/burp/.java:Z" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:Z \
    -e DISPLAY="${DISPLAY:-:0}" \
    --security-opt label=type:container_runtime_t \
    --userns=keep-id \
    --net=host \
    burp-suite-pro

# Wait for Burp Suite to be ready
for i in {1..30}; do
    if podman exec burp-pro curl -s "http://${BURP_HOST}:${BURP_PORT}/${BURP_APIKEY}/v0.1/scan" >/dev/null; then
        echo "Burp Suite is ready."
        break
    fi
    echo "Waiting for Burp Suite to start... ($i/30)"
    sleep 5
done

# Start scans for each target
for i in "${!TARGETS[@]}"; do
    TARGET="${TARGETS[$i]}"
    APP="${APP_NAME[$i]}"
    echo "Starting scan for ${TARGET}..."

    # Configure scan based on mode
    if [ "${MODE}" = "http" ]; then
        SCOPE="http://${TARGET}:80"
        URL="http://${TARGET}:${WEBPORT}"
    else
        SCOPE="https://${TARGET}:443"
        URL="https://${TARGET}:${WEBPORT}"
    fi

    # Initiate scan
    SCAN_ID=$(podman exec burp-pro curl -s -X POST "http://${BURP_HOST}:${BURP_PORT}/${BURP_APIKEY}/v0.1/scan" \
        -d "{\"scope\":{\"include\":[{\"rule\":\"${SCOPE}\"}],\"type\":\"SimpleScope\"},\"urls\":[\"${URL}\"]}" \
        | jq -r '.scan_id' 2>/dev/null || echo "0")

    if [ "${SCAN_ID}" = "0" ]; then
        echo "Error: Failed to start scan for ${TARGET}"
        continue
    fi

    # Monitor scan progress
    while true; do
        STATUS=$(podman exec burp-pro curl -s "http://${BURP_HOST}:${BURP_PORT}/${BURP_APIKEY}/v0.1/scan/${SCAN_ID}" \
            | jq -r '.crawl_and_audit.status // "unknown"')
        echo "[${TARGET}] Scan #${SCAN_ID} Status: ${STATUS}"
        if [[ "${STATUS}" != *"remaining"* ]]; then
            break
        fi
        sleep 15
    done

    # Retrieve scan results
    podman exec burp-pro curl -s "http://${BURP_HOST}:${BURP_PORT}/${BURP_APIKEY}/v0.1/scan/${SCAN_ID}" \
        | jq -r '.issue_events[].issue | "[" + .severity + "] " + .name + " - " + .origin + .path' \
        | sort -u > "${RESULT_DIR}/burpsuite-${APP}-${SCAN_ID}.log"
done

# Copy results and clean up
podman cp burp-pro:/home/burp/.java "${RESULT_DIR}"
podman stop burp-pro >/dev/null 2>&1 || true
echo "Burp Suite scan completed."