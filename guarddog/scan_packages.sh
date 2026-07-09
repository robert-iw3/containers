#!/bin/bash

# Configuration
CONFIG_FILE="./packages.yaml"
OFFLOAD_DIR="./guarddog-results"
LOG_FILE="./scan.log"
MAX_PARALLEL=4
TIMEOUT=300
CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-podman}"  # override with env var if needed

if ! command -v yq &> /dev/null; then
    echo "ERROR: yq is required. Please install it."
    exit 1
fi

log_message() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1" | tee -a "$LOG_FILE"
}

read_packages() {
    if [ ! -f "$CONFIG_FILE" ]; then
        log_message "ERROR: Configuration file $CONFIG_FILE not found"
        exit 1
    fi

    mapfile -t D_PKG < <(yq e '.packages[].name' "$CONFIG_FILE")
    mapfile -t R_NAME < <(yq e '.packages[].result_name // .name' "$CONFIG_FILE")
    mapfile -t ECOS  < <(yq e '.packages[].ecosystem // "pypi"' "$CONFIG_FILE")
}

cleanup() {
    log_message "Cleaning up..."
    $CONTAINER_RUNTIME stop guarddog 2>/dev/null || true
}

trap cleanup EXIT INT TERM

main() {
    mkdir -p "$OFFLOAD_DIR"
    touch "$LOG_FILE"
    log_message "Starting GuardDog scanning process..."

    read_packages

    if [ ${#D_PKG[@]} -eq 0 ]; then
        log_message "ERROR: No packages found in configuration"
        exit 1
    fi

    log_message "Building guarddog image..."
    $CONTAINER_RUNTIME build -t guarddog .

    log_message "Starting guarddog container..."
    $CONTAINER_RUNTIME run --rm -d --name guarddog \
        --user $(id -u):$(id -g) \
        -v "$OFFLOAD_DIR:/guarddog-results:Z" \
        guarddog tail -f /dev/null

    log_message "Scanning ${#D_PKG[@]} packages in parallel (max $MAX_PARALLEL)..."
    for ((i=0; i<${#D_PKG[@]}; i++)); do
        (
            output_file="${OFFLOAD_DIR}/${R_NAME[$i]}.json"
            eco="${ECOS[$i]}"
            pkg_name="${D_PKG[$i]}"
            log_message "Scanning $eco package: $pkg_name"

            if $CONTAINER_RUNTIME exec guarddog timeout $TIMEOUT guarddog "$eco" scan "$pkg_name" --output-format=json > "$output_file" 2>> "$LOG_FILE"; then
                log_message "Completed $eco scan: $pkg_name"
            else
                log_message "ERROR: Failed $eco scan: $pkg_name"
                echo '{"error": "scan failed", "package": "'"$pkg_name"'"}' > "$output_file"
            fi
        ) &

        if (( (i + 1) % MAX_PARALLEL == 0 )); then
            wait
        fi
    done
    wait

    log_message "All scans completed. Results in $OFFLOAD_DIR"
}

main 2>> "$LOG_FILE"