# Combined Boundary controller + worker configuration.
#
# __PLACEHOLDER__ values are rendered from environment variables at container
# start by the docker-compose command wrapper (see docker-compose.yml), so no
# key material is baked into the image. The AEAD KMS blocks are for dev/UAT;
# use a cloud KMS (awskms/azurekeyvault/gcpckms/transit) in production:
# https://developer.hashicorp.com/boundary/docs/configuration/kms

disable_mlock = true

controller {
  name        = "boundary-controller-0"
  description = "Boundary controller"

  database {
    url = "env://BOUNDARY_POSTGRES_URL"
  }
}

# combined controller+worker process: upstream must be a DNS name pointing
# at the local cluster listener (bare IPs are rejected when they differ from
# the listener address)
worker {
  name              = "boundary-worker-0"
  description       = "Boundary worker"
  public_addr       = "__BOUNDARY_PUBLIC_HOST__"
  initial_upstreams = ["localhost:9201"]
}

# API; front with TLS-terminating LB or set tls_cert_file/tls_key_file in production
listener "tcp" {
  address     = "0.0.0.0"
  purpose     = "api"
  tls_disable = true
}

# controller <-> worker
listener "tcp" {
  address     = "0.0.0.0"
  purpose     = "cluster"
  tls_disable = true
}

# client -> worker session proxy
listener "tcp" {
  address     = "0.0.0.0"
  purpose     = "proxy"
  tls_disable = true
}

# health/metrics endpoint (:9203/health, :9203/metrics)
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
