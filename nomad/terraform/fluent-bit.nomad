job "fluent-bit" {
  datacenters = ["dc1"]
  type        = "system"

  group "fluent-bit" {
    task "fluent-bit" {
      driver = "podman"

      config {
        image = "fluent/fluent-bit:3.1.9"
        args = [
          "/fluent-bit/bin/fluent-bit",
          "-c",
          "/fluent-bit/etc/fluent-bit.conf"
        ]
        volumes = [
          "local/fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf"
        ]
      }

      template {
        data = <<EOH
[INPUT]
    Name              tail
    Path              /var/log/nomad/nomad.log
    Tag               nomad.log

[INPUT]
    Name              tail
    Path              /var/log/consul/consul.log
    Tag               consul.log

[INPUT]
    Name              tail
    Path              /var/log/vault/vault.log
    Tag               vault.log

[OUTPUT]
    Name              stdout
    Match             *

[OUTPUT]
    Name              prometheus_exporter
    Match             *
    Host              0.0.0.0
    Port              2021
    Metrics_uri       /metrics
EOH
        destination = "local/fluent-bit.conf"
      }

      resources {
        cpu    = 500
        memory = 256
      }

      service {
        name = "fluent-bit"
        port = "metrics"
        tags = ["metrics"]

        check {
          type     = "http"
          path     = "/metrics"
          port     = "metrics"
          interval = "10s"
          timeout  = "2s"
        }
      }

      network {
        port "metrics" {
          to = 2021
        }
      }
    }
  }
}