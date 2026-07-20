# Portal Boundary: combined controller + worker.
# __PLACEHOLDER__ values are rendered from .env at container start.

disable_mlock = true

controller {
  name        = "portal-controller"
  description = "Dev portal Boundary controller"

  database {
    url = "env://BOUNDARY_POSTGRES_URL"
  }
}

worker {
  name              = "portal-worker"
  description       = "Dev portal Boundary worker"
  public_addr       = "__BOUNDARY_PUBLIC_ADDR__"
  initial_upstreams = ["localhost:9201"]
}

listener "tcp" {
  address       = "0.0.0.0"
  purpose       = "api"
  tls_cert_file = "/portal-certs/boundary.crt"
  tls_key_file  = "/portal-certs/boundary.key"
}

listener "tcp" {
  address     = "0.0.0.0"
  purpose     = "cluster"
  tls_disable = true
}

listener "tcp" {
  address     = "0.0.0.0"
  purpose     = "proxy"
  tls_disable = true
}

listener "tcp" {
  address       = "0.0.0.0"
  purpose       = "ops"
  tls_cert_file = "/portal-certs/boundary.crt"
  tls_key_file  = "/portal-certs/boundary.key"
}

kms "aead" {
  purpose   = "root"
  aead_type = "aes-gcm"
  key       = "__BOUNDARY_ROOT_KEY__"
  key_id    = "global_root"
}

kms "aead" {
  purpose   = "worker-auth"
  aead_type = "aes-gcm"
  key       = "__BOUNDARY_WORKER_AUTH_KEY__"
  key_id    = "global_worker-auth"
}

kms "aead" {
  purpose   = "recovery"
  aead_type = "aes-gcm"
  key       = "__BOUNDARY_RECOVERY_KEY__"
  key_id    = "global_recovery"
}
