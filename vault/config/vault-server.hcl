api_addr                = "https://0.0.0.0:8200"
cluster_addr            = "https://0.0.0.0:8201"
cluster_name            = "vault-cluster"
disable_mlock           = false
ui                      = true

listener "tcp" {
    address       = "0.0.0.0:8200"
    tls_cert_file = "/certs/vault-0.crt.pem"
    tls_key_file  = "/certs/vault-0.key.pem"
}

service_registration "consul" {
    address = "0.0.0.0:8501"
    scheme  = "https"
}

storage "consul" {
    address = "0.0.0.0:8501"
    path    = "vault"
}