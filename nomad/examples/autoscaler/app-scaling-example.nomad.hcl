# Horizontal app scaling: a `scaling` block inside any service job's group is
# picked up by the autoscaler automatically — works on every avenue, no cloud
# APIs needed.
job "webapp" {
  datacenters = ["dc1"]
  type        = "service"

  group "web" {
    count = 2

    scaling {
      enabled = true
      min     = 2
      max     = 10

      policy {
        cooldown            = "2m"
        evaluation_interval = "30s"

        check "avg_cpu" {
          source = "prometheus"
          query  = "avg(nomad_client_allocs_cpu_total_percent{exported_job=\"webapp\"})"

          strategy "target-value" {
            target = 70
          }
        }
      }
    }

    network {
      port "http" {
        to = 8080
      }
    }

    task "app" {
      driver = "podman"

      config {
        image = "docker.io/traefik/whoami:v1.11.0"
        ports = ["http"]
      }

      resources {
        cpu    = 100
        memory = 128
      }
    }
  }
}
