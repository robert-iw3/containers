#!/bin/bash

METHOD="$1"  # e.g., --method terraform (or bash, python, all)

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
  --method terraform) run_splunk; run_terraform; run_test ;;
  --method bash) run_splunk; run_bash; run_test ;;
  --method python) run_splunk; run_python; run_test ;;
  --method all)
    run_splunk
    run_terraform
    run_bash
    run_python
    run_test
    ;;
  *)
    echo "Usage: ./orchestrate.sh --method [terraform|bash|python|all]"
    exit 1
    ;;
esac

log "Orchestration complete"