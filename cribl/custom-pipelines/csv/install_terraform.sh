#!/bin/bash

LOG_FILE="install_terraform.log"
QUERIES_DIR="./csv_files"

log() {
  local level="$1"
  shift
  echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $*" | tee -a "$LOG_FILE"
}

if command -v terraform &> /dev/null; then
  log "INFO" "Terraform already installed. Version: $(terraform --version)"
else
  log "INFO" "Installing Terraform..."
  sudo apt-get update -y || { log "ERROR" "Failed to update"; exit 1; }
  sudo apt-get install -y gnupg software-properties-common curl || { log "ERROR" "Failed prereqs"; exit 1; }
  curl -fsSL https://apt.releases.hashicorp/gpg | sudo apt-key add - || { log "ERROR" "GPG failed"; exit 1; }
  sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp $(lsb_release -cs) main" || { log "ERROR" "Repo failed"; exit 1; }
  sudo apt-get update -y || { log "ERROR" "Update failed"; exit 1; }
  sudo apt-get install terraform -y || { log "ERROR" "Install failed"; exit 1; }
  log "INFO" "Terraform installed: $(terraform --version)"
fi

if [ ! -d "$QUERIES_DIR" ]; then
  mkdir -p "$QUERIES_DIR"
  log "INFO" "Created $QUERIES_DIR"
fi

if [ -f "orchestrate.sh" ]; then
  log "INFO" "Running orchestrate.sh --method all"
  chmod +x orchestrate.sh
  ./orchestrate.sh --method all || { log "ERROR" "Orchestrate failed"; exit 1; }
else
  log "ERROR" "orchestrate.sh not found"
  exit 1
fi

log "INFO" "Setup complete"