variable "kubeconfig_path" {
  description = "Path to kubeconfig file"
  type        = string
  default     = "~/.kube/config"
}

variable "namespace" {
  type        = string
  default     = "kagami"
}

variable "release_name" {
  type        = string
  default     = "kagami"
}

variable "chart_path" {
  type        = string
  default     = "../../../helm/kagami"
}

variable "image_repository" {
  type        = string
  default     = "ghcr.io/awkronos/kagami"
}

variable "image_tag" {
  type        = string
  default     = "develop"
}

variable "allowed_origins" {
  type        = string
}

variable "redis_url" {
  type        = string
}

variable "database_url" {
  type        = string
}

variable "public_url" {
  type        = string
}

variable "ws_broadcast_concurrency" {
  type    = number
  default = 128
}

variable "ws_broadcast_timeout_ms" {
  type    = number
  default = 300
}

variable "room_broadcast_hz" {
  type    = number
  default = 20
}

variable "ws_bridge_channels" {
  type    = string
  default = "room.presentation,holodeck.scene,holodeck.camera.pose,intent.*,narrative.created,forge.progress"
}
