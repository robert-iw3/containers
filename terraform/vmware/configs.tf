# Rendered product configurations. __PRIVATE_IP__ and __HOSTNAME__ are
# substituted on each node at boot by the install script.

locals {
  consul_config = <<-EOT
    datacenter       = "${var.consul_datacenter}"
    server           = true
    bootstrap_expect = ${length(var.consul_ips)}
    data_dir         = "/opt/consul/data"
    node_name        = "__HOSTNAME__"
    bind_addr        = "__PRIVATE_IP__"
    advertise_addr   = "__PRIVATE_IP__"
    client_addr      = "0.0.0.0"
    encrypt          = "${random_bytes.consul_gossip.base64}"
    retry_join       = ${jsonencode(var.consul_ips)}

    ui_config { enabled = true }

    ports {
      https    = 8501
      grpc_tls = 8503
    }

    tls {
      defaults {
        verify_incoming = false
        verify_outgoing = true
        ca_file         = "/etc/consul.d/tls/ca.pem"
        cert_file       = "/etc/consul.d/tls/cert.pem"
        key_file        = "/etc/consul.d/tls/key.pem"
      }
      internal_rpc {
        verify_incoming        = true
        verify_server_hostname = true
      }
    }

    auto_encrypt { allow_tls = true }

    acl {
      enabled                  = true
      default_policy           = "deny"
      down_policy              = "extend-cache"
      enable_token_persistence = true
    }

    connect { enabled = true }
  EOT

  vault_retry_join = join("\n", [for ip in var.vault_ips : <<-EOT
      retry_join {
        leader_api_addr       = "https://${ip}:8200"
        leader_tls_servername = "vault.internal"
        leader_ca_cert_file   = "/etc/vault.d/tls/ca.pem"
      }
  EOT
  ])

  # Shamir seal: `vault operator init` after first boot. For automated
  # unseal on-prem, point a `seal "transit"` stanza at an existing Vault.
  vault_config = <<-EOT
    ui            = true
    disable_mlock = true
    cluster_name  = "${var.name_prefix}"
    api_addr      = "https://__PRIVATE_IP__:8200"
    cluster_addr  = "https://__PRIVATE_IP__:8201"

    listener "tcp" {
      address         = "0.0.0.0:8200"
      cluster_address = "0.0.0.0:8201"
      tls_cert_file   = "/etc/vault.d/tls/cert.pem"
      tls_key_file    = "/etc/vault.d/tls/key.pem"
      tls_min_version = "tls12"
    }

    storage "raft" {
      path    = "/opt/vault/data"
      node_id = "__HOSTNAME__"

    ${local.vault_retry_join}
    }

    telemetry {
      disable_hostname          = true
      prometheus_retention_time = "12h"
    }
  EOT

  boundary_controller_config = <<-EOT
    disable_mlock = true

    controller {
      name        = "__HOSTNAME__"
      description = "Boundary controller"

      database {
        url = "env://BOUNDARY_POSTGRES_URL"
      }

      public_cluster_addr = "__PRIVATE_IP__:9201"
    }

    listener "tcp" {
      address     = "0.0.0.0"
      purpose     = "api"
      tls_disable = true
    }

    listener "tcp" {
      address = "0.0.0.0"
      purpose = "cluster"
    }

    listener "tcp" {
      address     = "0.0.0.0"
      purpose     = "ops"
      tls_disable = true
    }

    kms "aead" {
      purpose   = "root"
      aead_type = "aes-gcm"
      key       = "${random_bytes.boundary_root.base64}"
      key_id    = "global_root"
    }

    kms "aead" {
      purpose   = "worker-auth"
      aead_type = "aes-gcm"
      key       = "${random_bytes.boundary_worker_auth.base64}"
      key_id    = "global_worker-auth"
    }

    kms "aead" {
      purpose   = "recovery"
      aead_type = "aes-gcm"
      key       = "${random_bytes.boundary_recovery.base64}"
      key_id    = "global_recovery"
    }
  EOT

  boundary_worker_config = <<-EOT
    disable_mlock = true

    worker {
      name              = "__HOSTNAME__"
      description       = "Boundary worker"
      public_addr       = "__PRIVATE_IP__:9202"
      initial_upstreams = ["${var.boundary_controller_ip}:9201"]
    }

    listener "tcp" {
      address = "0.0.0.0"
      purpose = "proxy"
    }

    kms "aead" {
      purpose   = "worker-auth"
      aead_type = "aes-gcm"
      key       = "${random_bytes.boundary_worker_auth.base64}"
      key_id    = "global_worker-auth"
    }
  EOT

  postgres_user_data = <<-EOT
    #!/usr/bin/env bash
    set -euxo pipefail
    export DEBIAN_FRONTEND=noninteractive
    for i in 1 2 3; do apt-get update -y && break || sleep 10; done
    apt-get install -y postgresql postgresql-contrib
    PG_VER=$(ls /etc/postgresql | head -1)
    echo "listen_addresses = '*'" >> "/etc/postgresql/$PG_VER/main/postgresql.conf"
    echo "host all boundary 0.0.0.0/0 scram-sha-256" >> "/etc/postgresql/$PG_VER/main/pg_hba.conf"
    systemctl restart postgresql
    sudo -u postgres psql -c "CREATE ROLE boundary LOGIN PASSWORD '${random_password.boundary_db.result}';"
    sudo -u postgres psql -c "CREATE DATABASE boundary OWNER boundary;"
  EOT
}

module "consul_userdata" {
  source          = "../modules/hashicorp-install"
  product         = "consul"
  product_version = var.consul_version
  exec_start      = "/usr/local/bin/consul agent -config-dir=/etc/consul.d"
  config          = local.consul_config

  extra_files = {
    "/etc/consul.d/tls/ca.pem"   = module.consul_ca.ca_cert_pem
    "/etc/consul.d/tls/cert.pem" = module.consul_ca.cert_pem
    "/etc/consul.d/tls/key.pem"  = module.consul_ca.key_pem
  }
}

module "vault_userdata" {
  source          = "../modules/hashicorp-install"
  product         = "vault"
  product_version = var.vault_version
  exec_start      = "/usr/local/bin/vault server -config=/etc/vault.d/server.hcl"
  config          = local.vault_config

  extra_files = {
    "/etc/vault.d/tls/ca.pem"   = module.vault_ca.ca_cert_pem
    "/etc/vault.d/tls/cert.pem" = module.vault_ca.cert_pem
    "/etc/vault.d/tls/key.pem"  = module.vault_ca.key_pem
  }
}

module "boundary_controller_userdata" {
  source          = "../modules/hashicorp-install"
  product         = "boundary"
  product_version = var.boundary_version
  exec_start      = "/usr/local/bin/boundary server -config=/etc/boundary.d/server.hcl"
  config          = local.boundary_controller_config
  env_content     = "BOUNDARY_POSTGRES_URL=postgresql://boundary:${random_password.boundary_db.result}@${var.postgres_ip}:5432/boundary"

  extra_setup = <<-EOT
    for i in $(seq 1 120); do
      (echo > /dev/tcp/${var.postgres_ip}/5432) 2>/dev/null && break
      sleep 5
    done
    set -a; . /etc/boundary.d/boundary.env; set +a
    sudo -E -u boundary /usr/local/bin/boundary database init \
      -config /etc/boundary.d/server.hcl > /var/log/boundary-db-init.log 2>&1 \
      || grep -qi 'already.*initialized' /var/log/boundary-db-init.log
    chmod 0600 /var/log/boundary-db-init.log
  EOT
}

module "boundary_worker_userdata" {
  source          = "../modules/hashicorp-install"
  product         = "boundary"
  product_version = var.boundary_version
  exec_start      = "/usr/local/bin/boundary server -config=/etc/boundary.d/server.hcl"
  config          = local.boundary_worker_config
}
