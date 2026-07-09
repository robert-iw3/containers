job "fluent-bit" {
  datacenters = ["dc1"]
  type = "system"

  group "fluent-bit" {
    task "fluent-bit" {
      driver = "podman"
      config {
        image = "fluent/fluent-bit:latest"
        args = ["/fluent-bit/bin/fluent-bit", "-c", "/fluent-bit/etc/fluent-bit.conf"]
      }
      resources {
        cpu    = 100
        memory = 128
      }
      template {
        data = <<EOH
[SERVICE]
    Flush        1
    Log_Level    info
    Parsers_File parsers.conf

[INPUT]
    Name         tail
    Path         /var/log/nomad/nomad.log
    Tag          nomad

[OUTPUT]
    Name         stdout
    Match        *
EOH
        destination = "local/fluent-bit.conf"
      }
    }
  }
}