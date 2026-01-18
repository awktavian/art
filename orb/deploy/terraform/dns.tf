# =============================================================================
# Kagami DNS Configuration
# Terraform for GCP Cloud DNS
# Created: January 5, 2026
# =============================================================================

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "kagami_domain" {
  description = "Primary Kagami domain"
  default     = "awkronos.com"
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token for awkronos.com"
  sensitive   = true
}

# -----------------------------------------------------------------------------
# GCP Cloud DNS Zone for awkronos.com
# -----------------------------------------------------------------------------

resource "google_dns_managed_zone" "kagami_dev" {
  name        = "kagami-dev"
  dns_name    = "awkronos.com."
  description = "Kagami protocol domain"
  
  dnssec_config {
    state = "on"
  }
}

# -----------------------------------------------------------------------------
# A Records - Point to Cloud Run
# -----------------------------------------------------------------------------

# Root domain
resource "google_dns_record_set" "kagami_root" {
  name         = "awkronos.com."
  managed_zone = google_dns_managed_zone.kagami_dev.name
  type         = "A"
  ttl          = 300
  
  rrdatas = [
    # Cloud Run regional IPs (us-west1)
    "216.239.32.21",
    "216.239.34.21",
    "216.239.36.21",
    "216.239.38.21"
  ]
}

# API subdomain
resource "google_dns_record_set" "kagami_api" {
  name         = "api.awkronos.com."
  managed_zone = google_dns_managed_zone.kagami_dev.name
  type         = "CNAME"
  ttl          = 300
  rrdatas      = ["ghs.googlehosted.com."]
}

# WebSocket subdomain
resource "google_dns_record_set" "kagami_ws" {
  name         = "ws.awkronos.com."
  managed_zone = google_dns_managed_zone.kagami_dev.name
  type         = "CNAME"
  ttl          = 300
  rrdatas      = ["ghs.googlehosted.com."]
}

# Voice subdomain
resource "google_dns_record_set" "kagami_voice" {
  name         = "voice.awkronos.com."
  managed_zone = google_dns_managed_zone.kagami_dev.name
  type         = "CNAME"
  ttl          = 300
  rrdatas      = ["ghs.googlehosted.com."]
}

# CDN subdomain (Cloud Storage)
resource "google_dns_record_set" "kagami_cdn" {
  name         = "cdn.awkronos.com."
  managed_zone = google_dns_managed_zone.kagami_dev.name
  type         = "CNAME"
  ttl          = 300
  rrdatas      = ["c.storage.googleapis.com."]
}

# Docs subdomain
resource "google_dns_record_set" "kagami_docs" {
  name         = "docs.awkronos.com."
  managed_zone = google_dns_managed_zone.kagami_dev.name
  type         = "CNAME"
  ttl          = 300
  rrdatas      = ["c.storage.googleapis.com."]
}

# -----------------------------------------------------------------------------
# TXT Records - Verification
# -----------------------------------------------------------------------------

resource "google_dns_record_set" "kagami_txt" {
  name         = "awkronos.com."
  managed_zone = google_dns_managed_zone.kagami_dev.name
  type         = "TXT"
  ttl          = 300
  rrdatas = [
    "\"google-site-verification=PLACEHOLDER\"",
    "\"v=spf1 include:_spf.google.com ~all\""
  ]
}

# -----------------------------------------------------------------------------
# MX Records (if we want email on awkronos.com)
# -----------------------------------------------------------------------------

# resource "google_dns_record_set" "kagami_mx" {
#   name         = "awkronos.com."
#   managed_zone = google_dns_managed_zone.kagami_dev.name
#   type         = "MX"
#   ttl          = 300
#   rrdatas = [
#     "1 aspmx.l.google.com.",
#     "5 alt1.aspmx.l.google.com.",
#     "5 alt2.aspmx.l.google.com.",
#     "10 alt3.aspmx.l.google.com.",
#     "10 alt4.aspmx.l.google.com."
#   ]
# }

# -----------------------------------------------------------------------------
# Cloud Run Domain Mapping
# -----------------------------------------------------------------------------

resource "google_cloud_run_domain_mapping" "api" {
  location = var.region
  name     = "api.awkronos.com"
  
  metadata {
    namespace = var.project
  }
  
  spec {
    route_name = "kagami-api"
  }
}

resource "google_cloud_run_domain_mapping" "ws" {
  location = var.region
  name     = "ws.awkronos.com"
  
  metadata {
    namespace = var.project
  }
  
  spec {
    route_name = "kagami-realtime"
  }
}

resource "google_cloud_run_domain_mapping" "voice" {
  location = var.region
  name     = "voice.awkronos.com"
  
  metadata {
    namespace = var.project
  }
  
  spec {
    route_name = "kagami-voice"
  }
}

# -----------------------------------------------------------------------------
# SSL Certificates (Google-managed)
# -----------------------------------------------------------------------------

resource "google_compute_managed_ssl_certificate" "kagami" {
  name = "kagami-ssl-cert"
  
  managed {
    domains = [
      "awkronos.com",
      "api.awkronos.com",
      "ws.awkronos.com",
      "voice.awkronos.com",
      "cdn.awkronos.com",
      "docs.awkronos.com"
    ]
  }
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "kagami_nameservers" {
  description = "Nameservers to configure at Cloudflare"
  value       = google_dns_managed_zone.kagami_dev.name_servers
}

output "kagami_api_url" {
  description = "API URL"
  value       = "https://api.awkronos.com"
}

output "kagami_ws_url" {
  description = "WebSocket URL"
  value       = "wss://ws.awkronos.com"
}

output "kagami_voice_url" {
  description = "Voice streaming URL"
  value       = "wss://voice.awkronos.com"
}
