# Defguard Gateway instance configuration
resource "aws_instance" "defguard_gateway" {
  ami           = var.ami
  instance_type = var.instance_type

  user_data = templatefile("${path.module}/setup.py", {
    gateway_port     = var.gateway_port
    network_id       = var.network_id
    core_address     = var.core_address
    core_grpc_port   = var.core_grpc_port
    package_version  = var.package_version
    nat              = var.nat
    gateway_name     = "defguard-gateway-${var.network_id}"
    arch             = var.arch
    log_level        = var.log_level
    secrets_manager_arn = var.secrets_manager_arn
  })
  user_data_replace_on_change = true

  primary_network_interface {
    network_interface_id = var.network_interface_id
  }

  tags = {
    Name = "defguard-gateway-instance-${var.network_id}"
  }

  depends_on = [var.secrets_manager_secret_version]
}