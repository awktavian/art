terraform {
  required_version = ">= 1.5.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }
  }
}

provider "kubernetes" {
  config_path = var.kubeconfig_path
}

provider "helm" {
  kubernetes {
    config_path = var.kubeconfig_path
  }
}

module "kagami" {
  source = "../../modules/kagami_helm"

  namespace        = var.namespace
  release_name     = var.release_name
  chart_path       = var.chart_path
  image_repository = var.image_repository
  image_tag        = var.image_tag
  environment      = "staging"
  allowed_origins  = var.allowed_origins
  redis_url        = var.redis_url
  database_url     = var.database_url
  public_url       = var.public_url

  ws_broadcast_concurrency = var.ws_broadcast_concurrency
  ws_broadcast_timeout_ms  = var.ws_broadcast_timeout_ms
  room_broadcast_hz        = var.room_broadcast_hz
  ws_bridge_channels       = var.ws_bridge_channels
}
