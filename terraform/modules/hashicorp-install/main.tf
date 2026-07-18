terraform {
  required_version = ">= 1.5.0"
}

locals {
  user_data = templatefile("${path.module}/templates/install.sh.tpl", {
    product         = var.product
    product_version = var.product_version
    config          = var.config
    exec_start      = var.exec_start
    extra_files     = var.extra_files
    env_content     = var.env_content
    extra_setup     = var.extra_setup
  })
}
