locals {
  consul_tag  = "${var.name_prefix}-consul-server"
  vault_tag   = "${var.name_prefix}-vault-server"
  common_tags = merge(var.tags, { project = var.name_prefix })

  # static controller address so worker configs can reference it without a
  # dependency cycle through the NIC for_each
  boundary_controller_ip = cidrhost(cidrsubnet(var.vnet_cidr, 8, 0), 10)
}

resource "azurerm_resource_group" "this" {
  name     = "${var.name_prefix}-rg"
  location = var.location
  tags     = local.common_tags
}

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

resource "azurerm_virtual_network" "this" {
  name                = "${var.name_prefix}-vnet"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = [var.vnet_cidr]
  tags                = local.common_tags
}

resource "azurerm_subnet" "main" {
  name                 = "${var.name_prefix}-main"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [cidrsubnet(var.vnet_cidr, 8, 0)]
}

resource "azurerm_subnet" "db" {
  name                 = "${var.name_prefix}-db"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [cidrsubnet(var.vnet_cidr, 8, 1)]

  delegation {
    name = "postgres"
    service_delegation {
      name    = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_network_security_group" "this" {
  name                = "${var.name_prefix}-nsg"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.common_tags

  dynamic "security_rule" {
    for_each = length(var.allowed_admin_cidrs) > 0 ? {
      ssh          = { port = "22", priority = 200 }
      vault        = { port = "8200", priority = 210 }
      consul_http  = { port = "8500", priority = 220 }
      consul_https = { port = "8501", priority = 230 }
      boundary     = { port = "9200-9203", priority = 240 }
    } : {}

    content {
      name                       = security_rule.key
      priority                   = security_rule.value.priority
      direction                  = "Inbound"
      access                     = "Allow"
      protocol                   = "Tcp"
      source_port_range          = "*"
      destination_port_range     = security_rule.value.port
      source_address_prefixes    = var.allowed_admin_cidrs
      destination_address_prefix = "*"
    }
  }
}

resource "azurerm_subnet_network_security_group_association" "main" {
  subnet_id                 = azurerm_subnet.main.id
  network_security_group_id = azurerm_network_security_group.this.id
}

# ---------------------------------------------------------------------------
# Key Vault: auto-unseal + Boundary KMS
# ---------------------------------------------------------------------------

resource "random_string" "kv" {
  length  = 6
  upper   = false
  special = false
}

resource "azurerm_key_vault" "this" {
  name                     = "${substr(replace(var.name_prefix, "-", ""), 0, 17)}${random_string.kv.result}"
  location                 = azurerm_resource_group.this.location
  resource_group_name      = azurerm_resource_group.this.name
  tenant_id                = data.azurerm_client_config.current.tenant_id
  sku_name                 = "standard"
  purge_protection_enabled = false
  tags                     = local.common_tags
}

resource "azurerm_key_vault_access_policy" "deployer" {
  key_vault_id = azurerm_key_vault.this.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  key_permissions = ["Create", "Get", "List", "Delete", "Purge", "GetRotationPolicy"]
}

resource "azurerm_key_vault_key" "keys" {
  for_each = toset(["vault-unseal", "boundary-root", "boundary-worker-auth", "boundary-recovery"])

  name         = each.key
  key_vault_id = azurerm_key_vault.this.id
  key_type     = "RSA"
  key_size     = 2048
  key_opts     = ["decrypt", "encrypt", "sign", "unwrapKey", "verify", "wrapKey"]

  depends_on = [azurerm_key_vault_access_policy.deployer]
}

# ---------------------------------------------------------------------------
# Boundary database (PostgreSQL flexible server, private access)
# ---------------------------------------------------------------------------

resource "random_password" "boundary_db" {
  length  = 32
  special = false
}

resource "azurerm_private_dns_zone" "db" {
  name                = "${var.name_prefix}.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.common_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "db" {
  name                  = "${var.name_prefix}-db-link"
  resource_group_name   = azurerm_resource_group.this.name
  private_dns_zone_name = azurerm_private_dns_zone.db.name
  virtual_network_id    = azurerm_virtual_network.this.id
}

resource "azurerm_postgresql_flexible_server" "boundary" {
  name                          = "${var.name_prefix}-boundary-db"
  location                      = azurerm_resource_group.this.location
  resource_group_name           = azurerm_resource_group.this.name
  version                       = "16"
  administrator_login           = "boundary"
  administrator_password        = random_password.boundary_db.result
  sku_name                      = var.db_sku
  storage_mb                    = 32768
  delegated_subnet_id           = azurerm_subnet.db.id
  private_dns_zone_id           = azurerm_private_dns_zone.db.id
  public_network_access_enabled = false
  zone                          = "1"
  tags                          = local.common_tags

  depends_on = [azurerm_private_dns_zone_virtual_network_link.db]
}

resource "azurerm_postgresql_flexible_server_database" "boundary" {
  name      = "boundary"
  server_id = azurerm_postgresql_flexible_server.boundary.id
}

# ---------------------------------------------------------------------------
# Shared secrets and TLS
# ---------------------------------------------------------------------------

resource "random_bytes" "consul_gossip" {
  length = 32
}

module "consul_ca" {
  source      = "../modules/internal-ca"
  common_name = "server.${var.datacenter}.consul"
  dns_sans    = ["server.${var.datacenter}.consul", "localhost"]
}

module "vault_ca" {
  source      = "../modules/internal-ca"
  common_name = "vault.internal"
  dns_sans    = ["vault.internal", "localhost"]
}

# ---------------------------------------------------------------------------
# Virtual machines
# ---------------------------------------------------------------------------

locals {
  vms = merge(
    { for i in range(var.consul_servers) : "consul-${i}" => {
      role      = local.consul_tag
      user_data = module.consul_userdata.user_data
    } },
    { for i in range(var.vault_servers) : "vault-${i}" => {
      role      = local.vault_tag
      user_data = module.vault_userdata.user_data
    } },
    { "boundary-controller" = {
      role      = "${var.name_prefix}-boundary-controller"
      user_data = module.boundary_controller_userdata.user_data
    } },
    { for i in range(var.boundary_workers) : "boundary-worker-${i}" => {
      role      = "${var.name_prefix}-boundary-worker"
      user_data = module.boundary_worker_userdata.user_data
    } },
  )
}

resource "azurerm_public_ip" "vm" {
  for_each = local.vms

  name                = "${var.name_prefix}-${each.key}-pip"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.common_tags
}

resource "azurerm_network_interface" "vm" {
  for_each = local.vms

  name                = "${var.name_prefix}-${each.key}-nic"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.common_tags

  ip_configuration {
    name                          = "primary"
    subnet_id                     = azurerm_subnet.main.id
    private_ip_address_allocation = each.key == "boundary-controller" ? "Static" : "Dynamic"
    private_ip_address            = each.key == "boundary-controller" ? local.boundary_controller_ip : null
    public_ip_address_id          = azurerm_public_ip.vm[each.key].id
  }
}

resource "azurerm_linux_virtual_machine" "vm" {
  for_each = local.vms

  name                  = "${var.name_prefix}-${each.key}"
  location              = azurerm_resource_group.this.location
  resource_group_name   = azurerm_resource_group.this.name
  size                  = var.vm_size
  admin_username        = var.admin_username
  network_interface_ids = [azurerm_network_interface.vm[each.key].id]
  custom_data           = base64encode(each.value.user_data)
  tags                  = merge(local.common_tags, { role = each.value.role })

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.admin_ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  identity {
    type = "SystemAssigned"
  }
}

# cloud auto-join (go-discover) reads VM tags via the Azure API
resource "azurerm_role_assignment" "reader" {
  for_each = local.vms

  scope                = azurerm_resource_group.this.id
  role_definition_name = "Reader"
  principal_id         = azurerm_linux_virtual_machine.vm[each.key].identity[0].principal_id
}

resource "azurerm_key_vault_access_policy" "vm" {
  for_each = local.vms

  key_vault_id = azurerm_key_vault.this.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_linux_virtual_machine.vm[each.key].identity[0].principal_id

  key_permissions = ["Get", "WrapKey", "UnwrapKey"]
}
