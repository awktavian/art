terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

variable "project" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "GCP region"
}

variable "app_name" {
  type        = string
  default     = "kagami"
  description = "Application name"
}

variable "environment_name" {
  type        = string
  default     = "dev"
  description = "Environment (dev, staging, prod)"
}

variable "container_image" {
  type        = string
  default     = "kagami/kagami-hub:latest"
  description = "Container image"
}

variable "jwt_secret" {
  type        = string
  default     = ""
  sensitive   = true
  description = "JWT secret"
}

variable "kagami_api_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Kagami API key"
}

resource "google_container_cluster" "gke" {
  name     = "${var.app_name}-${var.environment_name}"
  location = var.region

  remove_default_node_pool = true
  initial_node_count       = 1

  networking_mode = "VPC_NATIVE"
}

resource "google_container_node_pool" "default" {
  name       = "system"
  location   = var.region
  cluster    = google_container_cluster.gke.name
  node_count = 2

  autoscaling {
    min_node_count = 2
    max_node_count = 10
  }

  node_config {
    preemptible  = false
    machine_type = "e2-standard-2"
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

data "google_client_config" "current" {}

provider "kubernetes" {
  host                   = "https://${google_container_cluster.gke.endpoint}"
  token                  = data.google_client_config.current.access_token
  cluster_ca_certificate = base64decode(google_container_cluster.gke.master_auth[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = "https://${google_container_cluster.gke.endpoint}"
    token                  = data.google_client_config.current.access_token
    cluster_ca_certificate = base64decode(google_container_cluster.gke.master_auth[0].cluster_ca_certificate)
  }
}

resource "helm_release" "kagami" {
  name       = "kagami"
  namespace  = "default"
  repository = "file://../../helm/kagami"
  chart      = "kagami"
  values = [yamlencode({
    image = {
      repository = var.container_image
      tag        = null
      pullPolicy = "IfNotPresent"
    }
    service = { type = "LoadBalancer", port = 80, targetPort = 8001 }
    env = {
      ENVIRONMENT      = var.environment_name
      KAGAMI_PUBLIC_URL = ""
      PORT             = "8000"
    }
    secrets = {
      jwtSecret      = var.jwt_secret
      kagamiApiKey  = var.kagami_api_key
    }
  })]
  depends_on = [google_container_node_pool.default]
}
