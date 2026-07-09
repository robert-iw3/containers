api_addr                = "https://0.0.0.0:8200"
cluster_addr            = "https://0.0.0.0:8201"
cluster_name            = "vault-cluster"
disable_mlock           = false
ui                      = true

listener "tcp" {
    address       = "0.0.0.0:8200"
    tls_cert_file = "/certs/vault.crt.pem"
    tls_key_file  = "/certs/vault.key.pem"
}

service_registration "consul" {
    address = "0.0.0.0:8501"
    token = "your consul token here"
    scheme = "https"
}

storage "raft" {
    path    = "/vault/data"
    node_id = "vault-minimal"
}