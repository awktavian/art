terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
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

provider "azurerm" {
  features {}
}

variable "app_name" { type = string  default = "kagami" }
variable "environment_name" { type = string  default = "dev" }
variable "location" { type = string  default = "eastus" }
variable "container_image" { type = string }
variable "jwt_secret" { type = string  sensitive = true }
variable "kagami_api_key" { type = string  sensitive = true }
variable "node_count" { type = number  default = 2 }

resource "azurerm_resource_group" "rg" {
  name     = "${var.app_name}-${var.environment_name}-rg"
  location = var.location
}

resource "azurerm_container_registry" "acr" {
  name                = replace("${var.app_name}${var.environment_name}acr", "-", "")
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = false
}

resource "azurerm_kubernetes_cluster" "aks" {
  name                = "${var.app_name}-${var.environment_name}-aks"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  dns_prefix          = "${var.app_name}-${var.environment_name}"

  default_node_pool {
    name       = "system"
    node_count = var.node_count
    vm_size    = "Standard_B2s"
    enable_auto_scaling = true
    min_count           = 2
    max_count           = 10
  }

  identity {
    type = "SystemAssigned"
  }

  tags = {
    Project     = var.app_name
    Environment = var.environment_name
  }
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
}

provider "kubernetes" {
  host                   = azurerm_kubernetes_cluster.aks.kube_config[0].host
  client_certificate     = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_certificate)
  client_key             = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_key)
  cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = azurerm_kubernetes_cluster.aks.kube_config[0].host
    client_certificate     = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_certificate)
    client_key             = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_key)
    cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].cluster_ca_certificate)
  }
}

# Helm release (wired; apply only when you are ready to deploy)
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

  depends_on = [azurerm_role_assignment.acr_pull]
}
