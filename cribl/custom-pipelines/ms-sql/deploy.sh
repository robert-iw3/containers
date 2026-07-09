#!/bin/bash

# Deploy script for end-to-end Cribl orchestration

LOG_FILE="deploy.log"

log() {
  local level="$1"
  shift
  echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $*" | tee -a "$LOG_FILE"
}

# Function to get orchestration method from user input or argument
get_method() {
  if [ -n "$1" ]; then
    METHOD="$1"
  else
    echo "Enter orchestration method (terraform, bash, python, all):"
    read METHOD || { log "ERROR" "Failed to read user input"; exit 1; }
    if [ -z "$METHOD" ]; then
      log "ERROR" "Method input cannot be empty"
      exit 1
    fi
  fi

  case "$METHOD" in
    terraform|bash|python|all) ;;
    *) log "ERROR" "Invalid method: $METHOD. Use terraform, bash, python, or all."; exit 1 ;;
  esac
}

# Parse argument if provided
get_method "$1"

# Check for config
if [ ! -f "config/config.ini" ]; then
  log "ERROR" "config/config.ini not found"
  exit 1
fi

# Check for required scripts and directories
REQUIRED_FILES=("install_terraform.sh" "orchestrate.sh")
for file in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "$file" ]; then
    log "ERROR" "Required file $file not found"
    exit 1
  fi
done

REQUIRED_DIRS=("splunk" "test" "python" "bash" "terraform" "queries" "config")
for dir in "${REQUIRED_DIRS[@]}"; do
  if [ ! -d "$dir" ]; then
    log "WARN" "Directory $dir not found, but proceeding if not critical"
  fi
done

# Install Terraform if needed
log "INFO" "Starting Terraform installation if needed"
if [ -x "./install_terraform.sh" ]; then
  ./install_terraform.sh || { log "ERROR" "Terraform installation failed"; exit 1; }
else
  log "ERROR" "install_terraform.sh is not executable"
  exit 1
fi

# Install Python deps if needed (for python method)
if [[ "$METHOD" == "python" || "$METHOD" == "all" ]]; then
  if command -v pip &> /dev/null && [ -f "python/requirements.txt" ]; then
    log "INFO" "Installing Python dependencies"
    pip install -r python/requirements.txt || { log "ERROR" "Python deps install failed"; exit 1; }
  else
    log "WARN" "pip not found or requirements.txt missing; skipping Python deps"
  fi
fi

# Install jq if needed for JSON handling (used in tests/scripts)
if ! command -v jq &> /dev/null; then
  log "INFO" "Installing jq"
  if command -v sudo &> /dev/null && command -v apt-get &> /dev/null; then
    sudo apt-get update -y && sudo apt-get install -y jq || { log "ERROR" "jq install failed"; exit 1; }
  else
    log "ERROR" "sudo or apt-get not available for jq installation"
    exit 1
  fi
fi

# Run Splunk integration (optional, if [splunk] in INI)
if grep -q "\[splunk\]" config/config.ini; then
  log "INFO" "Running Splunk configuration"
  if [ -d "splunk" ] && [ -f "splunk/configure_splunk.sh" ] && [ -x "splunk/configure_splunk.sh" ]; then
    cd splunk || { log "ERROR" "Failed to cd to splunk"; exit 1; }
    ./configure_splunk.sh || { log "ERROR" "Splunk config failed"; exit 1; }
    cd .. || { log "ERROR" "Failed to cd back"; exit 1; }
  else
    log "ERROR" "Splunk directory or script not found/executable"
    exit 1
  fi
fi

# Run orchestration with user-specified method
log "INFO" "Running orchestration with method: $METHOD"
if [ -x "./orchestrate.sh" ]; then
  ./orchestrate.sh --method $METHOD || { log "ERROR" "Orchestration failed"; exit 1; }
else
  log "ERROR" "orchestrate.sh is not executable"
  exit 1
fi

# Run tests
log "INFO" "Running validation tests"
if [ -d "test" ] && [ -f "test/test_pipeline.sh" ] && [ -x "test/test_pipeline.sh" ] && [ -f "test/test_pipeline.py" ]; then
  cd test || { log "ERROR" "Failed to cd to test"; exit 1; }
  ./test_pipeline.sh || log "WARN" "Bash test failed"
  python test_pipeline.py || log "WARN" "Python test failed"
  cd .. || { log "ERROR" "Failed to cd back"; exit 1; }
else
  log "WARN" "Test directory or scripts not found/executable; skipping tests"
fi

log "INFO" "Deployment complete"