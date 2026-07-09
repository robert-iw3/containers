variable "docker_image_name" {
  description = "The name of the Docker image to use"
  type        = string
  default     = "ghcr.io/robert-iw3/nessus:latest"
}

data "docker_image" "local_image" {
  name = var.docker_image_name
}

resource "docker_image" "built_image" {
  name         = var.docker_image_name
  build {
    context    = "${path.module}/docker"
    dockerfile = "${path.module}/docker/Dockerfile"
  }
}