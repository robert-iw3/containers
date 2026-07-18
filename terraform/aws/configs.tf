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
    retry_join       = ["provider=aws tag_key=role tag_value=${local.consul_tag} region=${var.region}"]

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
        auto_join             = "provider=aws tag_key=role tag_value=${local.vault_tag} region=${var.region}"
        auto_join_scheme      = "https"
        leader_tls_servername = "vault.internal"
        leader_ca_cert_file   = "/etc/vault.d/tls/ca.pem"
      }
    }

    seal "awskms" {
      region     = "${var.region}"
      kms_key_id = "${aws_kms_key.vault_unseal.id}"
    }

    telemetry {
      disable_hostname          = true
      prometheus_retention_time = "12h"
    }
  EOT

  boundary_kms_controller = <<-EOT
    kms "awskms" {
      purpose    = "root"
      region     = "${var.region}"
      kms_key_id = "${aws_kms_key.boundary_root.id}"
    }

    kms "awskms" {
      purpose    = "worker-auth"
      region     = "${var.region}"
      kms_key_id = "${aws_kms_key.boundary_worker_auth.id}"
    }

    kms "awskms" {
      purpose    = "recovery"
      region     = "${var.region}"
      kms_key_id = "${aws_kms_key.boundary_recovery.id}"
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

    ${local.boundary_kms_controller}
  EOT

  boundary_worker_config = <<-EOT
    disable_mlock = true

    worker {
      name              = "__HOSTNAME__"
      description       = "Boundary worker"
      public_addr       = "__PRIVATE_IP__:9202"
      initial_upstreams = ["${aws_instance.boundary_controller.private_ip}:9201"]
    }

    listener "tcp" {
      address = "0.0.0.0"
      purpose = "proxy"
    }

    kms "awskms" {
      purpose    = "worker-auth"
      region     = "${var.region}"
      kms_key_id = "${aws_kms_key.boundary_worker_auth.id}"
    }
  EOT
}
