variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Primary deployment region."
  type        = string
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
  default     = "open-wearables-prod"
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

variable "secret_values" {
  description = "Initial values for Secret Manager secrets."
  type        = map(string)
  default     = {}
  sensitive   = true
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
  default     = "ow-vpc-prod"
}

variable "create_cloud_sql" {
  description = "Whether to use Cloud SQL."
  type        = bool
  default     = true
}

variable "create_vpc_connector" {
  description = "Whether to create a VPC access connector."
  type        = bool
  default     = true
}

variable "vpc_connector_name" {
  description = "Name of the VPC access connector."
  type        = string
  default     = null
}

variable "cloud_sql_db_name" {
  description = "Database name."
  type        = string
  default     = "open-wearables"
}

variable "cloud_sql_db_user" {
  description = "Database user."
  type        = string
  default     = "open_wearables"
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

variable "queue_configs" {
  description = "A map of queue keys to their configurations."
  type = map(object({
    max_dispatches_per_second = number
    max_concurrent_dispatches = number
    max_attempts              = number
    min_backoff               = string
    max_backoff               = string
  }))
  default = {
    default = {
      max_dispatches_per_second = 5
      max_concurrent_dispatches = 20
      max_attempts              = 10
      min_backoff               = "0.1s"
      max_backoff               = "3600s"
    }
  }
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

variable "backend_api_command" {
  description = "Command for the backend API service."
  type        = list(string)
  default     = null
}

variable "backend_worker_command" {
  description = "Command for the worker service."
  type        = list(string)
  default     = null
}

variable "backend_init_command" {
  description = "Command for the init job."
  type        = list(string)
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

variable "frontend_custom_domain" {
  description = "Custom domain name for the frontend service."
  type        = string
  default     = null
}

variable "backend_api_allow_unauthenticated" {
  description = "Whether to allow unauthenticated access to the backend API. The API handles its own JWT authentication, so Cloud Run IAM auth should remain disabled (true) to avoid blocking all requests."
  type        = bool
  default     = true
}

variable "frontend_allow_unauthenticated" {
  description = "Whether to allow unauthenticated access to the frontend service."
  type        = bool
  default     = true
}

variable "api_service_account_email" {
  description = "The service account email of the backend API."
  type        = string
  default     = null
}

variable "worker_service_account_email" {
  description = "The service account email of the backend worker."
  type        = string
  default     = null
}

variable "migrator_service_account_email" {
  description = "The service account email of the backend init job."
  type        = string
  default     = null
}

variable "scheduler_service_account_email" {
  description = "The service account email of the Cloud Scheduler."
  type        = string
  default     = null
}

variable "frontend_service_account_email" {
  description = "The service account email of the frontend."
  type        = string
  default     = null
}

variable "external_api_service_account_email" {
  description = "The service account email of an external API to grant invoker access."
  type        = string
  default     = null
}

variable "service_account_project_roles" {
  description = "A map of account_key to a list of roles to grant at the project level."
  type        = map(list(string))
  default     = null
}
