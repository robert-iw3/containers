# AWS EBS CSI controller plugin (terraform avenue). Requires:
#   - csi_enabled = true in terraform tfvars (grants the EC2 volume IAM permissions)
#   - a rootful container runtime on the clients running this job (CSI plugins
#     cannot run under rootless podman)
job "ebs-csi-controller" {
  datacenters = ["dc1"]
  type        = "service"

  group "controller" {
    count = 2

    task "plugin" {
      driver = "podman"

      config {
        image      = "public.ecr.aws/ebs-csi-driver/aws-ebs-csi-driver:v1.62.0"
        privileged = true

        args = [
          "controller",
          "--endpoint=unix://csi/csi.sock",
          "--logging-format=text",
          "--v=4",
        ]
      }

      csi_plugin {
        id        = "aws-ebs"
        type      = "controller"
        mount_dir = "/csi"
      }

      resources {
        cpu    = 200
        memory = 256
      }
    }
  }
}
