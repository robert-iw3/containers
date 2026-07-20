# Portal Vault: raft storage, TLS API, registers itself in the Consul catalog.

ui            = true
cluster_name  = "backstage-portal"
disable_mlock = true

api_addr     = "https://vault:8200"
cluster_addr = "https://vault:8201"

listener "tcp" {
  address         = "0.0.0.0:8200"
  cluster_address = "0.0.0.0:8201"
  tls_cert_file   = "/certs/vault-0.crt.pem"
  tls_key_file    = "/certs/vault-0.key.pem"
  tls_min_version = "tls12"
}

storage "raft" {
  path    = "/vault/data"
  node_id = "vault-0"
}

service_registration "consul" {
  address     = "consul:8501"
  scheme      = "https"
  tls_ca_file = "/portal-certs/ca.crt"
  service     = "vault"
}

log_level  = "info"
log_format = "json"
