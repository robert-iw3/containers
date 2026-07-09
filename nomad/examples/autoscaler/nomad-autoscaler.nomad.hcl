# Nomad Autoscaler agent. Reads scaling policies from job `scaling` blocks
# (horizontal app scaling, works on every avenue) and from /local/policies
# (cluster scaling — see cluster-scaling-policy.hcl.example for the AWS ASG
# variant, which also needs autoscaler_enabled = true in the terraform tfvars
# for IAM).
#
# The token is read from a Nomad Variable; create it first:
#   nomad var put nomad/jobs/nomad-autoscaler autoscaler_token=<acl token>
variable "nomad_addr" {
  type = string
}

variable "prometheus_addr" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

job "nomad-autoscaler" {
  datacenters = ["dc1"]
  type        = "service"

  group "autoscaler" {
    count = 1

    network {
      port "http" {
        to = 8080
      }
    }

    task "autoscaler" {
      driver = "podman"

      config {
        image = "docker.io/hashicorp/nomad-autoscaler:0.5.0"
        args  = ["agent", "-config", "/local/config.hcl", "-policy-dir", "/local/policies"]
        ports = ["http"]
      }

      template {
        destination = "local/config.hcl"
        data        = <<EOH
nomad {
  address = "${var.nomad_addr}"
  token   = "{{ with nomadVar "nomad/jobs/nomad-autoscaler" }}{{ .autoscaler_token }}{{ end }}"
}

apm "prometheus" {
  driver = "prometheus"
  config = {
    address = "${var.prometheus_addr}"
  }
}

target "aws-asg" {
  driver = "aws-asg"
  config = {
    aws_region = "${var.aws_region}"
  }
}

strategy "target-value" {
  driver = "target-value"
}
EOH
      }

      resources {
        cpu    = 200
        memory = 256
      }

      service {
        name     = "nomad-autoscaler"
        port     = "http"
        provider = "nomad"

        check {
          type     = "http"
          path     = "/v1/health"
          interval = "10s"
          timeout  = "3s"
        }
      }
    }
  }
}
