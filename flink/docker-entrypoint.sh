#!/bin/bash
set -e

COMMAND_STANDALONE="standalone-job"
COMMAND_HISTORY_SERVER="history-server"

# If unspecified, the hostname of the container is taken as the JobManager address
JOB_MANAGER_RPC_ADDRESS=${JOB_MANAGER_RPC_ADDRESS:-$(hostname -f)}
CONF_FILE_DIR="${FLINK_HOME}/conf"

# Structured logging function
log() {
    local level="$1"
    local message="$2"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $message"
}

drop_privs_cmd() {
    if [ $(id -u) != 0 ]; then
        # Don't need to drop privs if EUID != 0
        return
    elif [ -x /sbin/su-exec ]; then
        # Alpine
        echo su-exec flink
    else
        # Others
        echo gosu flink
    fi
}

copy_plugins_if_required() {
    if [ -z "$ENABLE_BUILT_IN_PLUGINS" ]; then
        log INFO "No built-in plugins specified"
        return 0
    fi

    log INFO "Enabling built-in plugins: $ENABLE_BUILT_IN_PLUGINS"
    IFS=';' read -ra plugins <<< "$ENABLE_BUILT_IN_PLUGINS"
    for plugin in "${plugins[@]}"; do
        plugin_name=${plugin%.jar}
        if [ ! -e "${FLINK_HOME}/opt/${plugin}" ]; then
            log ERROR "Plugin ${plugin} does not exist at ${FLINK_HOME}/opt/${plugin}"
            exit 1
        fi
        mkdir -p "${FLINK_HOME}/plugins/${plugin_name}"
        ln -fs "${FLINK_HOME}/opt/${plugin}" "${FLINK_HOME}/plugins/${plugin_name}/${plugin}"
        log INFO "Successfully enabled plugin ${plugin}"
    done
}

set_config_options() {
    local config_parser_script="$FLINK_HOME/bin/config-parser-utils.sh"
    local config_dir="$FLINK_HOME/conf"
    local bin_dir="$FLINK_HOME/bin"
    local lib_dir="$FLINK_HOME/lib"
    local config_params=()

    while [ $# -gt 0 ]; do
        local key="$1"
        local value="$2"
        config_params+=("-D${key}=${value}")
        shift 2
    done

    if [ ${#config_params[@]} -gt 0 ]; then
        if ! "${config_parser_script}" "${config_dir}" "${bin_dir}" "${lib_dir}" "${config_params[@]}"; then
            log ERROR "Failed to set configuration options"
            exit 1
        fi
        log INFO "Configuration options set: ${config_params[*]}"
    fi
}

prepare_configuration() {
    local config_options=()

    # Validate JOB_MANAGER_RPC_ADDRESS
    if [[ -z "$JOB_MANAGER_RPC_ADDRESS" ]]; then
        log ERROR "JOB_MANAGER_RPC_ADDRESS is not set"
        exit 1
    fi
    config_options+=("jobmanager.rpc.address" "${JOB_MANAGER_RPC_ADDRESS}")
    config_options+=("blob.server.port" "6124")
    config_options+=("query.server.port" "6125")

    if [ -n "${TASK_MANAGER_NUMBER_OF_TASK_SLOTS}" ]; then
        config_options+=("taskmanager.numberOfTaskSlots" "${TASK_MANAGER_NUMBER_OF_TASK_SLOTS}")
    fi

    # Add TLS configurations if enabled
    if [ "${ENABLE_TLS:-false}" = "true" ]; then
        if [[ -z "${FLINK_SSL_KEYSTORE}" || -z "${FLINK_SSL_TRUSTSTORE}" ]]; then
            log ERROR "TLS enabled but FLINK_SSL_KEYSTORE or FLINK_SSL_TRUSTSTORE not set"
            exit 1
        fi
        config_options+=("security.ssl.enabled" "true")
        config_options+=("security.ssl.keystore" "${FLINK_SSL_KEYSTORE}")
        config_options+=("security.ssl.truststore" "${FLINK_SSL_TRUSTSTORE}")
        log INFO "TLS configuration enabled"
    fi

    if [ ${#config_options[@]} -ne 0 ]; then
        set_config_options "${config_options[@]}"
    fi

    if [ -n "${FLINK_PROPERTIES}" ]; then
        process_flink_properties "${FLINK_PROPERTIES}"
    fi
}

process_flink_properties() {
    local flink_properties_content=$1
    local config_options=()

    local OLD_IFS="$IFS"
    IFS=$'\n'
    for prop in $flink_properties_content; do
        prop=$(echo $prop | tr -d '[:space:]')
        if [ -z "$prop" ]; then
            continue
        fi
        IFS=':' read -r key value <<< "$prop"
        value=$(echo $value | envsubst)
        if [[ -z "$key" || -z "$value" ]]; then
            log ERROR "Invalid FLINK_PROPERTIES format: $prop"
            exit 1
        fi
        config_options+=("$key" "$value")
    done
    IFS="$OLD_IFS"

    if [ ${#config_options[@]} -ne 0 ]; then
        set_config_options "${config_options[@]}"
    fi
}

maybe_enable_jemalloc() {
    if [ "${DISABLE_JEMALLOC:-false}" == "true" ]; then
        log INFO "Jemalloc disabled via DISABLE_JEMALLOC"
        return
    fi

    JEMALLOC_PATH="/usr/lib/$(uname -m)-linux-gnu/libjemalloc.so"
    if [ -f "$JEMALLOC_PATH" ]; then
        export LD_PRELOAD=$LD_PRELOAD:$JEMALLOC_PATH
        log INFO "Jemalloc enabled at $JEMALLOC_PATH"
    else
        log WARNING "Jemalloc library not found at $JEMALLOC_PATH, falling back to glibc"
    fi
}

# Main execution
log INFO "Starting Flink entrypoint script"

maybe_enable_jemalloc
copy_plugins_if_required
prepare_configuration

args=("$@")
if [ "$1" = "help" ]; then
    printf "Usage: $(basename "$0") (jobmanager|${COMMAND_STANDALONE}|taskmanager|${COMMAND_HISTORY_SERVER})\n"
    printf "    Or $(basename "$0") help\n\n"
    printf "Environment variables:\n"
    printf "  DISABLE_JEMALLOC: Set to 'true' to disable jemalloc (default: false)\n"
    printf "  ENABLE_TLS: Set to 'true' to enable TLS (requires FLINK_SSL_KEYSTORE and FLINK_SSL_TRUSTSTORE)\n"
    exit 0
elif [ "$1" = "jobmanager" ]; then
    args=("${args[@]:1}")
    log INFO "Starting Job Manager"
    exec $(drop_privs_cmd) "$FLINK_HOME/bin/jobmanager.sh" start-foreground "${args[@]}"
elif [ "$1" = ${COMMAND_STANDALONE} ]; then
    args=("${args[@]:1}")
    log INFO "Starting Standalone Job Manager"
    exec $(drop_privs_cmd) "$FLINK_HOME/bin/standalone-job.sh" start-foreground "${args[@]}"
elif [ "$1" = ${COMMAND_HISTORY_SERVER} ]; then
    args=("${args[@]:1}")
    log INFO "Starting History Server"
    exec $(drop_privs_cmd) "$FLINK_HOME/bin/historyserver.sh" start-foreground "${args[@]}"
elif [ "$1" = "taskmanager" ]; then
    args=("${args[@]:1}")
    log INFO "Starting Task Manager"
    exec $(drop_privs_cmd) "$FLINK_HOME/bin/taskmanager.sh" start-foreground "${args[@]}"
fi

args=("${args[@]}")
log INFO "Running in pass-through mode with args: ${args[*]}"
exec $(drop_privs_cmd) "${args[@]}"