variable "app_name" {
  description = "Application name for tagging and resource names"
  type        = string
  default     = "kagami"
}

variable "environment_name" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR for the VPC"
  type        = string
  default     = "10.80.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Public subnets CIDRs"
  type        = list(string)
  default     = ["10.80.1.0/24", "10.80.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "Private subnets CIDRs"
  type        = list(string)
  default     = ["10.80.11.0/24", "10.80.12.0/24"]
}

variable "enable_rds" {
  description = "Whether to create an RDS instance (PostgreSQL)"
  type        = bool
  default     = true
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "kagami"
}

variable "db_username" {
  description = "Master DB username"
  type        = string
  default     = "kagami_user"
}

variable "db_password" {
  description = "Master DB password (use TF_VAR_db_password or secret)"
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "Elasticache node type"
  type        = string
  default     = "cache.t4g.micro"
}

variable "desired_count" {
  description = "Number of ECS service tasks"
  type        = number
  default     = 2
}

variable "container_image" {
  description = "Container image for K os (e.g., ghcr.io/awkronos/kagami:latest)"
  type        = string
}

variable "public_url" {
  description = "Public base URL (used for KAGAMI_PUBLIC_URL)"
  type        = string
  default     = "https://example.com"
}

variable "jwt_secret" {
  description = "JWT secret"
  type        = string
  sensitive   = true
}

variable "kagami_api_key" {
  description = "API key"
  type        = string
  sensitive   = true
}

variable "csrf_secret" {
  description = "CSRF secret for form validation"
  type        = string
  sensitive   = true
}

# =============================================================================
# Cluster Configuration
# =============================================================================

variable "etcd_endpoints" {
  description = "etcd cluster endpoints (optional - uses Redis for coordination if not set)"
  type        = list(string)
  default     = []
}

variable "cluster_auto_failover" {
  description = "Enable automatic failover in cluster"
  type        = bool
  default     = true
}

variable "cluster_auto_rebalance" {
  description = "Enable automatic rebalancing in cluster"
  type        = bool
  default     = true
}

# =============================================================================
# TLS/SSL Configuration
# =============================================================================

variable "acm_certificate_arn" {
  description = "ARN of ACM certificate for HTTPS. Create with: aws acm request-certificate --domain-name api.example.com"
  type        = string
}

# =============================================================================
# Weaviate Configuration
# =============================================================================

variable "weaviate_api_key" {
  description = "API key for Weaviate authentication"
  type        = string
  sensitive   = true
}

variable "enable_weaviate" {
  description = "Whether to deploy Weaviate as a managed service"
  type        = bool
  default     = true
}

# =============================================================================
# Secret Management
# =============================================================================

variable "use_secrets_manager" {
  description = "Use AWS Secrets Manager instead of SSM Parameter Store (recommended for production)"
  type        = bool
  default     = true
}

variable "openai_api_key" {
  description = "OpenAI API key for LLM services"
  type        = string
  sensitive   = true
  default     = ""
}

variable "hf_token" {
  description = "HuggingFace token for model downloads"
  type        = string
  sensitive   = true
  default     = ""
}
