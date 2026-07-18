data "vsphere_datacenter" "this" {
  name = var.datacenter
}

data "vsphere_compute_cluster" "this" {
  name          = var.cluster
  datacenter_id = data.vsphere_datacenter.this.id
}

data "vsphere_datastore" "this" {
  name          = var.datastore
  datacenter_id = data.vsphere_datacenter.this.id
}

data "vsphere_network" "this" {
  name          = var.network
  datacenter_id = data.vsphere_datacenter.this.id
}

data "vsphere_virtual_machine" "template" {
  name          = var.template
  datacenter_id = data.vsphere_datacenter.this.id
}

# ---------------------------------------------------------------------------
# Secrets and TLS (no cloud KMS on-prem: Vault uses Shamir; Boundary uses
# AEAD keys generated here — they live in terraform state, protect it, or
# switch Boundary/Vault to a `transit` seal against an existing Vault)
# ---------------------------------------------------------------------------

resource "random_bytes" "consul_gossip" {
  length = 32
}

resource "random_bytes" "boundary_root" {
  length = 32
}

resource "random_bytes" "boundary_worker_auth" {
  length = 32
}

resource "random_bytes" "boundary_recovery" {
  length = 32
}

resource "random_password" "boundary_db" {
  length  = 32
  special = false
}

module "consul_ca" {
  source      = "../modules/internal-ca"
  common_name = "server.${var.consul_datacenter}.consul"
  dns_sans    = ["server.${var.consul_datacenter}.consul", "localhost"]
}

module "vault_ca" {
  source      = "../modules/internal-ca"
  common_name = "vault.internal"
  dns_sans    = ["vault.internal", "localhost"]
  ip_sans     = concat(["127.0.0.1"], var.vault_ips)
}

# ---------------------------------------------------------------------------
# Virtual machines
# ---------------------------------------------------------------------------

locals {
  vms = merge(
    { for i, ip in var.consul_ips : "consul-${i}" => {
      ip        = ip
      user_data = module.consul_userdata.user_data
    } },
    { for i, ip in var.vault_ips : "vault-${i}" => {
      ip        = ip
      user_data = module.vault_userdata.user_data
    } },
    { "boundary-controller" = {
      ip        = var.boundary_controller_ip
      user_data = module.boundary_controller_userdata.user_data
    } },
    { for i, ip in var.boundary_worker_ips : "boundary-worker-${i}" => {
      ip        = ip
      user_data = module.boundary_worker_userdata.user_data
    } },
    { "postgres" = {
      ip        = var.postgres_ip
      user_data = local.postgres_user_data
    } },
  )
}

resource "vsphere_virtual_machine" "vm" {
  for_each = local.vms

  name             = "${var.name_prefix}-${each.key}"
  resource_pool_id = data.vsphere_compute_cluster.this.resource_pool_id
  datastore_id     = data.vsphere_datastore.this.id
  folder           = var.folder

  num_cpus  = var.num_cpus
  memory    = var.memory_mb
  guest_id  = data.vsphere_virtual_machine.template.guest_id
  scsi_type = data.vsphere_virtual_machine.template.scsi_type
  firmware  = data.vsphere_virtual_machine.template.firmware

  network_interface {
    network_id   = data.vsphere_network.this.id
    adapter_type = data.vsphere_virtual_machine.template.network_interface_types[0]
  }

  disk {
    label            = "disk0"
    size             = max(var.disk_gb, data.vsphere_virtual_machine.template.disks[0].size)
    thin_provisioned = data.vsphere_virtual_machine.template.disks[0].thin_provisioned
  }

  clone {
    template_uuid = data.vsphere_virtual_machine.template.id
  }

  extra_config = {
    "guestinfo.metadata" = base64encode(templatefile("${path.module}/templates/metadata.yaml.tpl", {
      hostname      = "${var.name_prefix}-${each.key}"
      ip            = each.value.ip
      prefix_length = var.network_prefix_length
      gateway       = var.gateway
      dns_servers   = var.dns_servers
    }))
    "guestinfo.metadata.encoding" = "base64"
    "guestinfo.userdata"          = base64encode(each.value.user_data)
    "guestinfo.userdata.encoding" = "base64"
  }

  lifecycle {
    ignore_changes = [clone[0].template_uuid]
  }
}
