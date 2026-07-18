# Standalone Vault server with integrated (raft) storage.
# For the Consul-backed variant, see integration-demos/hashicorp-stack.

ui           = true
cluster_name = "vault-cluster"

# HashiCorp recommends disabling mlock when using integrated storage,
# and disabling swap on the host instead. It also allows the container
# to run with no-new-privileges and without CAP_IPC_LOCK.
disable_mlock = true

api_addr     = "https://vault.local:8200"
cluster_addr = "https://vault.local:8201"

listener "tcp" {
  address            = "0.0.0.0:8200"
  cluster_address    = "0.0.0.0:8201"
  tls_cert_file      = "/certs/vault-0.crt.pem"
  tls_key_file       = "/certs/vault-0.key.pem"
  tls_min_version    = "tls12"
  telemetry {
    unauthenticated_metrics_access = false
  }
}

storage "raft" {
  path    = "/vault/data"
  node_id = "vault-0"
}

telemetry {
  disable_hostname          = true
  prometheus_retention_time = "12h"
}

log_level  = "info"
log_format = "json"
