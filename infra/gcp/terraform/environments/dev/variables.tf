variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
  default     = ""
}

variable "region" {
  description = "Primary deployment region."
  type        = string
  default     = "europe-west1"
}

variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
  default     = "open-wearables"
}

variable "labels" {
  description = "Common labels applied to supported resources."
  type        = map(string)
  default     = {}
}

variable "artifact_registry_repository_id" {
  description = "Artifact Registry repository ID."
  type        = string
  default     = "open-wearables-dev"
}

variable "create_secrets" {
  description = "Whether to create Secret Manager secret placeholders."
  type        = bool
  default     = false
}

variable "secret_names" {
  description = "Secret IDs to create when create_secrets is true."
  type        = list(string)
  default     = []
}

variable "github_owner" {
  description = "GitHub repository owner."
  type        = string
  default     = ""
}

variable "github_repository_name" {
  description = "GitHub repository name."
  type        = string
  default     = ""
}

variable "branch_pattern" {
  description = "Branch pattern for triggers."
  type        = string
  default     = "^main$"
}

variable "scheduler_jobs" {
  description = "Cloud Scheduler jobs for periodic task execution."
  type = map(object({
    description                = string
    schedule                   = string
    time_zone                  = optional(string, "Etc/UTC")
    target_url                 = string
    oidc_service_account_email = string
    audience                   = optional(string)
    http_method                = optional(string, "POST")
    headers                    = optional(map(string), {})
    body                       = optional(string)
  }))
  default = {}
}

variable "create_network" {
  description = "Whether to create a dedicated VPC network."
  type        = bool
  default     = false
}

variable "network_name" {
  description = "Name of the VPC network."
  type        = string
  default     = "open-wearables-network"
}

variable "create_cloud_sql" {
  description = "Whether to use Cloud SQL."
  type        = bool
  default     = true
}

variable "cloud_sql_db_name" {
  description = "Database name."
  type        = string
  default     = "ow-db"
}

variable "cloud_sql_db_user" {
  description = "Database user."
  type        = string
  default     = "ow-user"
}

variable "cloud_sql_db_password" {
  description = "Database password (optional if managed outside)."
  type        = string
  default     = null
}

variable "create_memorystore" {
  description = "Whether to use Memorystore Redis."
  type        = bool
  default     = true
}

variable "enable_backend_api_service" {
  description = "Enable OW API service."
  type        = bool
  default     = true
}

variable "enable_worker_service" {
  description = "Enable OW Worker service."
  type        = bool
  default     = true
}

variable "enable_backend_init_job" {
  description = "Enable OW migration job."
  type        = bool
  default     = true
}

variable "enable_frontend_service" {
  description = "Enable OW Frontend service."
  type        = bool
  default     = false
}

variable "enable_cloud_tasks_dispatch" {
  description = "Enable Cloud Tasks."
  type        = bool
  default     = true
}

variable "create_default_scheduler_jobs" {
  description = "Create scheduler jobs."
  type        = bool
  default     = true
}

variable "worker_service_base_url" {
  description = "Base URL for internal worker (for Cloud Tasks)."
  type        = string
  default     = null
}

variable "backend_image" {
  description = "Docker image for backend."
  type        = string
  default     = null
}

variable "frontend_image" {
  description = "Docker image for frontend."
  type        = string
  default     = null
}

variable "backend_api_env" {
  type    = map(string)
  default = {}
}

variable "backend_worker_env" {
  type    = map(string)
  default = {}
}

variable "backend_init_env" {
  type    = map(string)
  default = {}
}

variable "frontend_env" {
  type    = map(string)
  default = {}
}

variable "backend_api_secret_env" {
  type    = map(object({ secret = string, version = optional(string, "latest") }))
  default = {}
}

variable "backend_worker_secret_env" {
  type    = map(object({ secret = string, version = optional(string, "latest") }))
  default = {}
}

variable "backend_init_secret_env" {
  type    = map(object({ secret = string, version = optional(string, "latest") }))
  default = {}
}

variable "frontend_secret_env" {
  type    = map(object({ secret = string, version = optional(string, "latest") }))
  default = {}
}

variable "external_api_service_account_email" {
  description = "The service account email of an external API to grant invoker access."
  type        = string
  default     = null
}
