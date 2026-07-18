# Rendered product configurations. __PRIVATE_IP__ and __HOSTNAME__ are
# substituted on each node at boot by the install script.

locals {
  consul_config = <<-EOT
    datacenter       = "${var.datacenter}"
    server           = true
    bootstrap_expect = ${var.consul_servers}
    data_dir         = "/opt/consul/data"
    node_name        = "__HOSTNAME__"
    bind_addr        = "__PRIVATE_IP__"
    advertise_addr   = "__PRIVATE_IP__"
    client_addr      = "0.0.0.0"
    encrypt          = "${random_bytes.consul_gossip.base64}"
    retry_join       = ["provider=gce project_name=${var.project_id} tag_value=${local.consul_tag}"]

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

      retry_join {
        auto_join             = "provider=gce project_name=${var.project_id} tag_value=${local.vault_tag}"
        auto_join_scheme      = "https"
        leader_tls_servername = "vault.internal"
        leader_ca_cert_file   = "/etc/vault.d/tls/ca.pem"
      }
    }

    seal "gcpckms" {
      project    = "${var.project_id}"
      region     = "${var.region}"
      key_ring   = "${google_kms_key_ring.this.name}"
      crypto_key = "vault-unseal"
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

    kms "gcpckms" {
      purpose    = "root"
      project    = "${var.project_id}"
      region     = "${var.region}"
      key_ring   = "${google_kms_key_ring.this.name}"
      crypto_key = "boundary-root"
    }

    kms "gcpckms" {
      purpose    = "worker-auth"
      project    = "${var.project_id}"
      region     = "${var.region}"
      key_ring   = "${google_kms_key_ring.this.name}"
      crypto_key = "boundary-worker-auth"
    }

    kms "gcpckms" {
      purpose    = "recovery"
      project    = "${var.project_id}"
      region     = "${var.region}"
      key_ring   = "${google_kms_key_ring.this.name}"
      crypto_key = "boundary-recovery"
    }
  EOT

  boundary_worker_config = <<-EOT
    disable_mlock = true

    worker {
      name              = "__HOSTNAME__"
      description       = "Boundary worker"
      public_addr       = "__PRIVATE_IP__:9202"
      initial_upstreams = ["${google_compute_address.boundary_controller.address}:9201"]
    }

    listener "tcp" {
      address = "0.0.0.0"
      purpose = "proxy"
    }

    kms "gcpckms" {
      purpose    = "worker-auth"
      project    = "${var.project_id}"
      region     = "${var.region}"
      key_ring   = "${google_kms_key_ring.this.name}"
      crypto_key = "boundary-worker-auth"
    }
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
  env_content     = "BOUNDARY_POSTGRES_URL=postgresql://boundary:${random_password.boundary_db.result}@${google_sql_database_instance.boundary.private_ip_address}:5432/boundary"

  extra_setup = <<-EOT
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
