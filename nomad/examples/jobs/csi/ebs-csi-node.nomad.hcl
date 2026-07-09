# AWS EBS CSI node plugin — runs on every client (system job). Same
# prerequisites as the controller job.
job "ebs-csi-node" {
  datacenters = ["dc1"]
  type        = "system"

  group "node" {
    task "plugin" {
      driver = "podman"

      config {
        image      = "public.ecr.aws/ebs-csi-driver/aws-ebs-csi-driver:v1.62.0"
        privileged = true

        args = [
          "node",
          "--endpoint=unix://csi/csi.sock",
          "--logging-format=text",
          "--v=4",
        ]
      }

      csi_plugin {
        id        = "aws-ebs"
        type      = "node"
        mount_dir = "/csi"
      }

      resources {
        cpu    = 200
        memory = 256
      }
    }
  }
}
