# Defguard Proxy instance configuration
resource "aws_instance" "defguard_proxy" {
  ami           = var.ami
  instance_type = var.instance_type

  user_data = templatefile("${path.module}/setup.py", {
    proxy_url       = var.proxy_url
    grpc_port       = var.grpc_port
    arch            = var.arch
    package_version = var.package_version
    http_port       = var.http_port
    log_level       = var.log_level
    secrets_manager_arn = var.secrets_manager_arn
  })
  user_data_replace_on_change = true

  primary_network_interface {
    network_interface_id = var.network_interface_id
  }

  tags = {
    Name = "defguard-proxy-instance"
  }

  depends_on = [var.secrets_manager_secret_version]
}