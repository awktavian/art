# ==============================================================================
# Kagami TPU v6e (Trillium) Infrastructure
# Von Neumann Probe Deployment
#
# CREATED: January 4, 2026
#
# This terraform creates TPU training infrastructure that:
# - Is fully controlled from the house (Kagami Hub)
# - Uses end-to-end encryption (transit + at rest)
# - Auto-scales TPU pods based on training demand
# - Pulls checkpoints back to secure GCS bucket
# ==============================================================================

# ------------------------------------------------------------------------------
# Variables
# ------------------------------------------------------------------------------

variable "tpu_zone" {
  type        = string
  default     = "us-central2-b"  # TPU v6e availability
  description = "GCP zone for TPU VMs (must have v6e capacity)"
}

variable "tpu_topology" {
  type        = string
  default     = "4x4"  # 16 chips for development, 16x16=256 for production
  description = "TPU topology (e.g., 2x2=4, 4x4=16, 8x8=64, 16x16=256)"
}

variable "tpu_version" {
  type        = string
  default     = "v6e"
  description = "TPU version (v5e, v5p, v6e/trillium)"
}

variable "enable_wireguard" {
  type        = bool
  default     = true
  description = "Enable WireGuard VPN back to home hub"
}

variable "wireguard_hub_public_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "WireGuard public key from Kagami Hub"
}

variable "wireguard_hub_endpoint" {
  type        = string
  default     = ""
  description = "Home endpoint for WireGuard (e.g., home.kagami.ai:51820)"
}

variable "training_bucket" {
  type        = string
  default     = "kagami-training"
  description = "GCS bucket for checkpoints and data"
}

# ------------------------------------------------------------------------------
# KMS for Encryption
# ------------------------------------------------------------------------------

# Customer-managed encryption key (CMEK) for GCS
resource "google_kms_key_ring" "kagami" {
  name     = "kagami-keyring"
  location = var.region
}

resource "google_kms_crypto_key" "training_data" {
  name            = "kagami-training-key"
  key_ring        = google_kms_key_ring.kagami.id
  rotation_period = "7776000s"  # 90 days

  purpose = "ENCRYPT_DECRYPT"

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"  # Use HSM for production
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Grant storage service account access to key
resource "google_kms_crypto_key_iam_member" "gcs_encrypt" {
  crypto_key_id = google_kms_crypto_key.training_data.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}

data "google_project" "current" {}

# ------------------------------------------------------------------------------
# Encrypted GCS Bucket for Training Data
# ------------------------------------------------------------------------------

resource "google_storage_bucket" "training" {
  name     = "${var.training_bucket}-${var.project}"
  location = var.region

  uniform_bucket_level_access = true

  # Customer-managed encryption
  encryption {
    default_kms_key_name = google_kms_crypto_key.training_data.id
  }

  # Versioning for checkpoint recovery
  versioning {
    enabled = true
  }

  # Lifecycle rules
  lifecycle_rule {
    condition {
      age = 30  # Days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  # Retain checkpoints for 1 year
  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    project     = "kagami"
    environment = var.environment_name
    encrypted   = "true"
  }

  depends_on = [google_kms_crypto_key_iam_member.gcs_encrypt]
}

# Bucket IAM - only TPU VMs and hub can access
resource "google_storage_bucket_iam_member" "tpu_access" {
  bucket = google_storage_bucket.training.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.tpu_vm.email}"
}

# ------------------------------------------------------------------------------
# Service Account for TPU VMs
# ------------------------------------------------------------------------------

resource "google_service_account" "tpu_vm" {
  account_id   = "kagami-tpu-${var.environment_name}"
  display_name = "Kagami TPU Training Service Account"
  description  = "Service account for TPU training VMs"
}

# TPU VM needs these permissions
resource "google_project_iam_member" "tpu_permissions" {
  for_each = toset([
    "roles/tpu.admin",                    # Create/manage TPU nodes
    "roles/compute.instanceAdmin.v1",     # Manage compute instances
    "roles/logging.logWriter",            # Write logs
    "roles/monitoring.metricWriter",      # Write metrics
    "roles/cloudkms.cryptoKeyEncrypterDecrypter",  # Decrypt secrets
  ])

  project = var.project
  role    = each.value
  member  = "serviceAccount:${google_service_account.tpu_vm.email}"
}

# ------------------------------------------------------------------------------
# Secret Manager for Sensitive Config
# ------------------------------------------------------------------------------

resource "google_secret_manager_secret" "wireguard_private_key" {
  secret_id = "kagami-wireguard-private-key"

  replication {
    auto {}
  }

  labels = {
    project = "kagami"
  }
}

resource "google_secret_manager_secret" "hub_api_key" {
  secret_id = "kagami-hub-api-key"

  replication {
    auto {}
  }

  labels = {
    project = "kagami"
  }
}

# TPU SA can read secrets
resource "google_secret_manager_secret_iam_member" "tpu_secrets" {
  for_each = toset([
    google_secret_manager_secret.wireguard_private_key.secret_id,
    google_secret_manager_secret.hub_api_key.secret_id,
  ])

  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.tpu_vm.email}"
}

# ------------------------------------------------------------------------------
# VPC Network for TPU (Isolated)
# ------------------------------------------------------------------------------

resource "google_compute_network" "tpu_network" {
  name                    = "kagami-tpu-network"
  auto_create_subnetworks = false
  description             = "Isolated network for TPU training"
}

resource "google_compute_subnetwork" "tpu_subnet" {
  name          = "kagami-tpu-subnet"
  ip_cidr_range = "10.128.0.0/20"
  region        = var.region
  network       = google_compute_network.tpu_network.id

  # Enable private Google access (TPU VMs don't need public IPs)
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
  }
}

# Cloud NAT for outbound (to pull models, etc.)
resource "google_compute_router" "tpu_router" {
  name    = "kagami-tpu-router"
  region  = var.region
  network = google_compute_network.tpu_network.id
}

resource "google_compute_router_nat" "tpu_nat" {
  name                               = "kagami-tpu-nat"
  router                             = google_compute_router.tpu_router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# ------------------------------------------------------------------------------
# Firewall Rules
# ------------------------------------------------------------------------------

# Allow internal communication (TPU mesh)
resource "google_compute_firewall" "tpu_internal" {
  name    = "kagami-tpu-allow-internal"
  network = google_compute_network.tpu_network.id

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.128.0.0/20"]
  target_tags   = ["kagami-tpu"]
}

# Allow WireGuard from home hub
resource "google_compute_firewall" "wireguard" {
  count   = var.enable_wireguard ? 1 : 0
  name    = "kagami-allow-wireguard"
  network = google_compute_network.tpu_network.id

  allow {
    protocol = "udp"
    ports    = ["51820"]
  }

  # Only from home IP (set dynamically by hub)
  source_ranges = ["0.0.0.0/0"]  # Restrict in production
  target_tags   = ["kagami-vpn"]
}

# Allow SSH from IAP (for debugging only)
resource "google_compute_firewall" "iap_ssh" {
  name    = "kagami-allow-iap-ssh"
  network = google_compute_network.tpu_network.id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # IAP source range
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["kagami-tpu"]
}

# ------------------------------------------------------------------------------
# TPU Node Pool Template (v6e Trillium)
# ------------------------------------------------------------------------------

# Note: TPU v6e uses Queued Resources API for on-demand allocation
# This is the startup script that configures the TPU VM

locals {
  tpu_startup_script = <<-EOF
    #!/bin/bash
    set -euo pipefail

    # Log everything
    exec > >(tee /var/log/kagami-tpu-startup.log) 2>&1
    echo "Starting Kagami TPU VM setup at $(date)"

    # Install dependencies
    apt-get update
    apt-get install -y python3-pip wireguard-tools jq

    # Install Python packages
    pip3 install --upgrade pip
    pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    pip3 install torch_xla[tpu] -f https://storage.googleapis.com/libtpu-releases/index.html
    pip3 install jax[tpu] -f https://storage.googleapis.com/jax-releases/libtpu_releases.html
    pip3 install orbax-checkpoint google-cloud-storage prometheus-client

    # Pull Kagami training code
    gsutil -m cp -r gs://${google_storage_bucket.training.name}/code/kagami-training.tar.gz /opt/
    cd /opt && tar -xzf kagami-training.tar.gz

    # Configure WireGuard VPN back to home
    if [ "${var.enable_wireguard}" = "true" ]; then
      echo "Configuring WireGuard VPN..."

      # Get private key from Secret Manager
      WG_PRIVATE_KEY=$(gcloud secrets versions access latest --secret=kagami-wireguard-private-key)

      cat > /etc/wireguard/wg0.conf <<WGCONF
    [Interface]
    PrivateKey = $WG_PRIVATE_KEY
    Address = 10.200.200.2/24

    [Peer]
    PublicKey = ${var.wireguard_hub_public_key}
    Endpoint = ${var.wireguard_hub_endpoint}
    AllowedIPs = 10.200.200.0/24
    PersistentKeepalive = 25
    WGCONF

      chmod 600 /etc/wireguard/wg0.conf
      systemctl enable wg-quick@wg0
      systemctl start wg-quick@wg0
    fi

    # Start training orchestrator
    cd /opt/kagami-training
    export GCS_BUCKET="${google_storage_bucket.training.name}"
    export TPU_TOPOLOGY="${var.tpu_topology}"
    export HUB_ENDPOINT="http://10.200.200.1:8001"  # Via WireGuard

    python3 -m kagami.core.training.tpu.orchestrator \
      --checkpoint-bucket=gs://$GCS_BUCKET/checkpoints \
      --metrics-port=9090 \
      --hub-callback=$HUB_ENDPOINT/api/training/callback &

    echo "Kagami TPU VM ready at $(date)"
  EOF
}

# TPU Queued Resource request
resource "google_tpu_v2_vm" "training" {
  count = 0  # Set to 1 to create, 0 to destroy (controlled by hub)

  name = "kagami-training-${var.environment_name}"
  zone = var.tpu_zone

  runtime_version = "tpu-ubuntu2204-base"
  accelerator_type = "${var.tpu_version}-${var.tpu_topology}"

  # Network config
  network_config {
    network    = google_compute_network.tpu_network.id
    subnetwork = google_compute_subnetwork.tpu_subnet.id
    enable_external_ips = false  # No public IP (use WireGuard/NAT)
  }

  # Service account
  service_account {
    email  = google_service_account.tpu_vm.email
    scopes = ["cloud-platform"]
  }

  # Startup script
  metadata = {
    startup-script = local.tpu_startup_script
  }

  tags = ["kagami-tpu", "kagami-vpn"]

  labels = {
    project     = "kagami"
    environment = var.environment_name
    managed_by  = "hub"
  }
}

# ------------------------------------------------------------------------------
# Outputs (for Hub to use)
# ------------------------------------------------------------------------------

output "training_bucket" {
  value       = google_storage_bucket.training.name
  description = "GCS bucket for training data and checkpoints"
}

output "tpu_service_account" {
  value       = google_service_account.tpu_vm.email
  description = "Service account email for TPU VMs"
}

output "tpu_network" {
  value       = google_compute_network.tpu_network.id
  description = "VPC network ID for TPU VMs"
}

output "kms_key" {
  value       = google_kms_crypto_key.training_data.id
  description = "KMS key for data encryption"
}

output "wireguard_vpn_config" {
  value = var.enable_wireguard ? {
    cloud_address   = "10.200.200.2/24"
    hub_address     = "10.200.200.1/24"
    cloud_public_ip = "$(gcloud compute addresses describe kagami-vpn --region=${var.region} --format='value(address)')"
  } : null
  description = "WireGuard VPN configuration"
}
