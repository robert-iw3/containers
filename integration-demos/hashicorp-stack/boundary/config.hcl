# Demo Boundary: combined controller + worker.
# __PLACEHOLDER__ values are rendered from .env at container start.

disable_mlock = true

controller {
  name        = "demo-controller"
  description = "Demo Boundary controller"

  database {
    url = "env://BOUNDARY_POSTGRES_URL"
  }
}

worker {
  name              = "demo-worker"
  description       = "Demo Boundary worker"
  public_addr       = "__BOUNDARY_PUBLIC_ADDR__"
  initial_upstreams = ["localhost:9201"]
}

listener "tcp" {
  address     = "0.0.0.0"
  purpose     = "api"
  tls_disable = true
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
  address     = "0.0.0.0"
  purpose     = "ops"
  tls_disable = true
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
