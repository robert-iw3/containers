locals {
  consul_tag    = "${var.name_prefix}-consul-server"
  vault_tag     = "${var.name_prefix}-vault-server"
  common_labels = merge(var.labels, { project = var.name_prefix })
}

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

resource "google_compute_network" "this" {
  name                    = "${var.name_prefix}-net"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "this" {
  name          = "${var.name_prefix}-subnet"
  network       = google_compute_network.this.id
  ip_cidr_range = var.subnet_cidr
  region        = var.region
}

resource "google_compute_firewall" "internal" {
  name    = "${var.name_prefix}-internal"
  network = google_compute_network.this.name

  allow {
    protocol = "tcp"
  }
  allow {
    protocol = "udp"
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = [var.subnet_cidr]
  target_tags   = [var.name_prefix]
}

resource "google_compute_firewall" "admin" {
  count   = length(var.allowed_admin_cidrs) > 0 ? 1 : 0
  name    = "${var.name_prefix}-admin"
  network = google_compute_network.this.name

  allow {
    protocol = "tcp"
    ports    = ["22", "8200", "8500", "8501", "9200-9203"]
  }

  source_ranges = var.allowed_admin_cidrs
  target_tags   = [var.name_prefix]
}

# ---------------------------------------------------------------------------
# Service account: auto-join + KMS
# ---------------------------------------------------------------------------

resource "google_service_account" "stack" {
  account_id   = "${var.name_prefix}-stack"
  display_name = "${var.name_prefix} hashicorp stack"
}

resource "google_project_iam_member" "compute_viewer" {
  project = var.project_id
  role    = "roles/compute.viewer"
  member  = "serviceAccount:${google_service_account.stack.email}"
}

resource "google_kms_key_ring" "this" {
  name     = "${var.name_prefix}-keyring"
  location = var.region
}

resource "google_kms_crypto_key" "keys" {
  for_each = toset(["vault-unseal", "boundary-root", "boundary-worker-auth", "boundary-recovery"])

  name     = each.key
  key_ring = google_kms_key_ring.this.id

  lifecycle {
    prevent_destroy = false
  }
}

resource "google_kms_key_ring_iam_member" "stack" {
  key_ring_id = google_kms_key_ring.this.id
  role        = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member      = "serviceAccount:${google_service_account.stack.email}"
}

# ---------------------------------------------------------------------------
# Boundary database (Cloud SQL PostgreSQL, private IP)
# ---------------------------------------------------------------------------

resource "google_compute_global_address" "sql" {
  name          = "${var.name_prefix}-sql-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.this.id
}

resource "google_service_networking_connection" "sql" {
  network                 = google_compute_network.this.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.sql.name]
}

resource "random_password" "boundary_db" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "boundary" {
  name             = "${var.name_prefix}-boundary-db"
  database_version = "POSTGRES_17"
  region           = var.region

  settings {
    tier = var.db_tier

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.this.id
    }
  }

  deletion_protection = false

  depends_on = [google_service_networking_connection.sql]
}

resource "google_sql_user" "boundary" {
  name     = "boundary"
  instance = google_sql_database_instance.boundary.name
  password = random_password.boundary_db.result
}

resource "google_sql_database" "boundary" {
  name     = "boundary"
  instance = google_sql_database_instance.boundary.name
}

# ---------------------------------------------------------------------------
# Shared secrets and TLS
# ---------------------------------------------------------------------------

resource "random_bytes" "consul_gossip" {
  length = 32
}

# reserved controller address so worker configs can reference it without a
# dependency cycle through the instance for_each
resource "google_compute_address" "boundary_controller" {
  name         = "${var.name_prefix}-boundary-controller"
  subnetwork   = google_compute_subnetwork.this.id
  address_type = "INTERNAL"
  region       = var.region
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
# Instances
# ---------------------------------------------------------------------------

locals {
  instances = merge(
    { for i in range(var.consul_servers) : "consul-${i}" => {
      join_tag  = local.consul_tag
      user_data = module.consul_userdata.user_data
    } },
    { for i in range(var.vault_servers) : "vault-${i}" => {
      join_tag  = local.vault_tag
      user_data = module.vault_userdata.user_data
    } },
    { "boundary-controller" = {
      join_tag  = "${var.name_prefix}-boundary-controller"
      user_data = module.boundary_controller_userdata.user_data
    } },
    { for i in range(var.boundary_workers) : "boundary-worker-${i}" => {
      join_tag  = "${var.name_prefix}-boundary-worker"
      user_data = module.boundary_worker_userdata.user_data
    } },
  )
}

resource "google_compute_instance" "vm" {
  for_each = local.instances

  name         = "${var.name_prefix}-${each.key}"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = [var.name_prefix, each.value.join_tag]
  labels       = local.common_labels

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
      size  = 20
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.this.id
    network_ip = each.key == "boundary-controller" ? google_compute_address.boundary_controller.address : null

    access_config {
      # ephemeral public IP for admin access; drop for private-only deployments
    }
  }

  metadata = {
    startup-script = each.value.user_data
  }

  service_account {
    email  = google_service_account.stack.email
    scopes = ["cloud-platform"]
  }
}
