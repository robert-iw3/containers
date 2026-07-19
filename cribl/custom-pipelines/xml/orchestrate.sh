#!/bin/bash
# Orchestrate pipeline provisioning: ./orchestrate.sh --method [terraform|bash|python|all]
set -euo pipefail

usage() {
  echo "Usage: ./orchestrate.sh --method [terraform|bash|python|all]"
  exit 1
}

[ "${1:-}" = "--method" ] && [ -n "${2:-}" ] || usage
METHOD="$2"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $*"
}

run_splunk() {
  log "Running Splunk integration"
  cd splunk
  ./configure_splunk.sh
  cd ..
}

run_terraform() {
  log "Running Terraform method"
  cd terraform
  ./setup_terraform.sh
  cd ..
}

run_bash() {
  log "Running Bash method"
  cd bash
  ./configure_cribl.sh
  cd ..
}

run_python() {
  log "Running Python method"
  cd python
  python configure_cribl.py
  cd ..
}

run_test() {
  log "Running tests"
  cd test
  ./test_pipeline.sh
  python test_pipeline.py
  cd ..
}

case "$METHOD" in
  terraform) run_splunk; run_terraform; run_test ;;
  bash) run_splunk; run_bash; run_test ;;
  python) run_splunk; run_python; run_test ;;
  all)
    run_splunk
    run_terraform
    run_bash
    run_python
    run_test
    ;;
  *)
    usage
    ;;
esac
