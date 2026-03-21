variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Primary region for regional resources."
  type        = string
}

variable "environment" {
  description = "Deployment environment name, such as dev or prod."
  type        = string
}

variable "name_prefix" {
  description = "Prefix used for resource naming."
  type        = string
  default     = "open-wearables"
}

variable "labels" {
  description = "Common labels applied to supported resources."
  type        = map(string)
  default     = {}
}

variable "enable_apis" {
  description = "Whether Terraform should enable required Google APIs."
  type        = bool
  default     = true
}

variable "activate_apis" {
  description = "Google APIs required by the GCP overlay."
  type        = list(string)
  default = [
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudtasks.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "redis.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "vpcaccess.googleapis.com",
  ]
}

variable "create_artifact_registry" {
  description = "Whether to create the Docker Artifact Registry repository."
  type        = bool
  default     = true
}

variable "artifact_registry_repository_id" {
  description = "Artifact Registry repository ID."
  type        = string
  default     = "open-wearables"
}

variable "artifact_registry_description" {
  description = "Artifact Registry repository description."
  type        = string
  default     = "Container images for Open Wearables deployments"
}

variable "create_service_accounts" {
  description = "Whether to create dedicated service accounts."
  type        = bool
  default     = true
}

variable "service_accounts" {
  description = "Service accounts used by the deployment."
  type = map(object({
    display_name = string
    description  = string
  }))
  default = {
    api = {
      display_name = "Open Wearables API"
      description  = "Runs the public Cloud Run API service"
    }
    worker = {
      display_name = "Open Wearables Worker"
      description  = "Runs internal async HTTP handlers on Cloud Run"
    }
    migrator = {
      display_name = "Open Wearables Migrator"
      description  = "Runs Cloud Run jobs for migrations and initialization"
    }
    scheduler = {
      display_name = "Open Wearables Scheduler"
      description  = "Invokes Cloud Scheduler HTTP targets"
    }
    deployer = {
      display_name = "Open Wearables Deployer"
      description  = "Deploys images and updates Cloud Run services"
    }
  }
}

variable "service_account_project_roles" {
  description = "A map of account_key to a list of roles to grant at the project level."
  type        = map(list(string))
  default     = {
    api = [
      "roles/cloudsql.client",
      "roles/redis.editor",
      "roles/secretmanager.secretAccessor",
      "roles/vpcaccess.user",
      "roles/cloudtasks.enqueuer",
      "roles/iam.serviceAccountUser",
      "roles/iam.serviceAccountTokenCreator",
    ]
    worker = [
      "roles/cloudsql.client",
      "roles/redis.editor",
      "roles/secretmanager.secretAccessor",
      "roles/vpcaccess.user",
      "roles/cloudtasks.enqueuer",
      "roles/iam.serviceAccountUser",
      "roles/iam.serviceAccountTokenCreator",
    ]
    migrator = [
      "roles/cloudsql.client",
      "roles/secretmanager.secretAccessor",
      "roles/vpcaccess.user",
    ]
    scheduler = [
      "roles/run.invoker",
    ]
  }
}

variable "queue_configs" {
  description = "Cloud Tasks queues used by the async migration path."
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
      min_backoff               = "5s"
      max_backoff               = "300s"
    }
    sdk_sync = {
      max_dispatches_per_second = 10
      max_concurrent_dispatches = 50
      max_attempts              = 8
      min_backoff               = "5s"
      max_backoff               = "120s"
    }
    garmin_backfill = {
      max_dispatches_per_second = 2
      max_concurrent_dispatches = 5
      max_attempts              = 20
      min_backoff               = "15s"
      max_backoff               = "600s"
    }
  }
}

variable "create_secrets" {
  description = "Whether to create Secret Manager secret placeholders."
  type        = bool
  default     = false
}

variable "secret_names" {
  description = "Secret Manager secret IDs to create without versions."
  type        = list(string)
  default     = [
    "polar_client_id",
    "polar_client_secret"
  ]
}

variable "secret_values" {
  description = "Map of secret names to their initial values. Warning: these will be stored in state."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "enable_cloud_build_triggers" {
  description = "Whether to create Cloud Build triggers."
  type        = bool
  default     = false
}

variable "github_owner" {
  description = "GitHub repository owner for Cloud Build triggers."
  type        = string
  default     = ""
}

variable "github_repository_name" {
  description = "GitHub repository name for Cloud Build triggers."
  type        = string
  default     = ""
}

variable "branch_pattern" {
  description = "Branch pattern to trigger Cloud Build (e.g. ^main$)."
  type        = string
  default     = "^main$"
}

variable "scheduler_jobs" {
  description = "Cloud Scheduler jobs for periodic task replacements."
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

############################################
# Networking
############################################

variable "create_network" {
  description = "Whether to create a dedicated VPC network."
  type        = bool
  default     = false
}

variable "network_name" {
  description = "Name of the VPC network to use or create."
  type        = string
  default     = null
}

variable "subnetwork_name" {
  description = "Name of the subnet to use or create."
  type        = string
  default     = null
}

variable "subnet_cidr" {
  description = "CIDR range for the subnetwork if created."
  type        = string
  default     = "10.10.0.0/24"
}

variable "create_vpc_connector" {
  description = "Whether to create a Serverless VPC Access connector."
  type        = bool
  default     = false
}

variable "vpc_connector_name" {
  description = "Name of the VPC connector to use or create."
  type        = string
  default     = null
}

variable "vpc_connector_machine_type" {
  description = "Machine type for the VPC connector."
  type        = string
  default     = "e2-micro"
}

variable "vpc_connector_min_instances" {
  description = "Min instances for the VPC connector."
  type        = number
  default     = 2
}

variable "vpc_connector_max_instances" {
  description = "Max instances for the VPC connector."
  type        = number
  default     = 3
}

############################################
# Cloud Run Services
############################################

variable "enable_backend_api_service" {
  description = "Whether to enable the backend API service."
  type        = bool
  default     = true
}

variable "backend_api_service_name" {
  description = "Override the backend API service name."
  type        = string
  default     = null
}

variable "backend_image" {
  description = "The Docker image for the backend services."
  type        = string
  default     = null
}

variable "backend_container_port" {
  description = "The port the backend container listens on."
  type        = number
  default     = 8000
}

variable "backend_api_ingress" {
  description = "Ingress settings for the backend API service."
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "backend_api_allow_unauthenticated" {
  description = "Whether to allow unauthenticated access to the backend API."
  type        = bool
  default     = true
}

variable "backend_api_timeout_seconds" {
  description = "The timeout for the backend API service."
  type        = number
  default     = 300
}

variable "backend_api_concurrency" {
  description = "The concurrency setting for the backend API service."
  type        = number
  default     = 80
}

variable "backend_api_min_instances" {
  description = "The minimum instance count for the backend API service."
  type        = number
  default     = 0
}

variable "backend_api_max_instances" {
  description = "The maximum instance count for the backend API service."
  type        = number
  default     = 10
}

variable "backend_api_resource_limits" {
  description = "Resource limits for the backend API service."
  type        = map(string)
  default = {
    cpu    = "1000m"
    memory = "512Mi"
  }
}

variable "backend_api_command" {
  description = "Command for the backend API service."
  type        = list(string)
  default     = null
}

variable "backend_api_args" {
  description = "Args for the backend API service."
  type        = list(string)
  default     = null
}

variable "backend_api_env" {
  description = "Environment variables for the backend API service."
  type        = map(string)
  default     = {}
}

variable "backend_api_secret_env" {
  description = "Secret environment variables for the backend API service."
  type        = map(object({ secret = string, version = optional(string, "latest") }))
  default     = {}
}

variable "enable_worker_service" {
  description = "Whether to enable the worker service."
  type        = bool
  default     = true
}

variable "backend_worker_service_name" {
  description = "Override the worker service name."
  type        = string
  default     = null
}

variable "backend_worker_ingress" {
  description = "Ingress settings for the worker service."
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_ONLY"
}

variable "worker_service_base_url" {
  description = "The base URL for the worker service."
  type        = string
  default     = null
}

variable "backend_worker_timeout_seconds" {
  description = "The timeout for the worker service."
  type        = number
  default     = 3600
}

variable "backend_worker_concurrency" {
  description = "The concurrency setting for the worker service."
  type        = number
  default     = 10
}

variable "backend_worker_min_instances" {
  description = "The minimum instance count for the worker service."
  type        = number
  default     = 0
}

variable "backend_worker_max_instances" {
  description = "The maximum instance count for the worker service."
  type        = number
  default     = 5
}

variable "backend_worker_resource_limits" {
  description = "Resource limits for the worker service."
  type        = map(string)
  default = {
    cpu    = "1000m"
    memory = "1024Mi"
  }
}

variable "backend_worker_command" {
  description = "Command for the worker service."
  type        = list(string)
  default     = null
}

variable "backend_worker_args" {
  description = "Args for the worker service."
  type        = list(string)
  default     = null
}

variable "backend_worker_env" {
  description = "Environment variables for the worker service."
  type        = map(string)
  default     = {}
}

variable "backend_worker_secret_env" {
  description = "Secret environment variables for the worker service."
  type        = map(object({ secret = string, version = optional(string, "latest") }))
  default     = {}
}

variable "enable_backend_init_job" {
  description = "Whether to enable the initialization job."
  type        = bool
  default     = true
}

variable "backend_init_job_name" {
  description = "Override the initialization job name."
  type        = string
  default     = null
}

variable "backend_init_timeout_seconds" {
  description = "The timeout for the initialization job."
  type        = number
  default     = 600
}

variable "backend_init_resource_limits" {
  description = "Resource limits for the initialization job."
  type        = map(string)
  default = {
    cpu    = "1000m"
    memory = "512Mi"
  }
}

variable "backend_init_command" {
  description = "Command for the initialization job."
  type        = list(string)
  default     = ["/app/scripts/start/cloud-run-init.sh"]
}

variable "backend_init_args" {
  description = "Args for the initialization job."
  type        = list(string)
  default     = []
}

variable "backend_init_env" {
  description = "Environment variables for the initialization job."
  type        = map(string)
  default     = {}
}

variable "backend_init_secret_env" {
  description = "Secret environment variables for the initialization job."
  type        = map(object({ secret = string, version = optional(string, "latest") }))
  default     = {}
}

variable "enable_frontend_service" {
  description = "Whether to enable the frontend service."
  type        = bool
  default     = false
}

variable "frontend_service_name" {
  description = "Override the frontend service name."
  type        = string
  default     = null
}

variable "frontend_image" {
  description = "The Docker image for the frontend service."
  type        = string
  default     = null
}

variable "frontend_container_port" {
  description = "The port the frontend container listens on."
  type        = number
  default     = 3000
}

variable "frontend_ingress" {
  description = "Ingress settings for the frontend service."
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "frontend_allow_unauthenticated" {
  description = "Whether to allow unauthenticated access to the frontend."
  type        = bool
  default     = true
}

variable "frontend_timeout_seconds" {
  description = "The timeout for the frontend service."
  type        = number
  default     = 60
}

variable "frontend_concurrency" {
  description = "The concurrency setting for the frontend service."
  type        = number
  default     = 100
}

variable "frontend_min_instances" {
  description = "The minimum instance count for the frontend service."
  type        = number
  default     = 0
}

variable "frontend_max_instances" {
  description = "The maximum instance count for the frontend service."
  type        = number
  default     = 5
}

variable "frontend_resource_limits" {
  description = "Resource limits for the frontend service."
  type        = map(string)
  default = {
    cpu    = "1000m"
    memory = "512Mi"
  }
}

variable "frontend_command" {
  description = "Command for the frontend service."
  type        = list(string)
  default     = null
}

variable "frontend_args" {
  description = "Args for the frontend service."
  type        = list(string)
  default     = null
}

variable "frontend_env" {
  description = "Environment variables for the frontend service."
  type        = map(string)
  default     = {}
}

variable "frontend_secret_env" {
  description = "Secret environment variables for the frontend service."
  type        = map(object({ secret = string, version = optional(string, "latest") }))
  default     = {}
}

variable "frontend_custom_domain" {
  description = "Custom domain name for the frontend service."
  type        = string
  default     = null
}

variable "backend_vpc_egress" {
  description = "VPC egress setting for the backend services."
  type        = string
  default     = "ALL_TRAFFIC"
}

############################################
# Service Account Overrides
############################################

variable "api_service_account_email" {
  description = "Override the API service account email."
  type        = string
  default     = null
}

variable "worker_service_account_email" {
  description = "Override the worker service account email."
  type        = string
  default     = null
}

variable "migrator_service_account_email" {
  description = "Override the migrator service account email."
  type        = string
  default     = null
}

variable "frontend_service_account_email" {
  description = "Override the frontend service account email."
  type        = string
  default     = null
}

variable "scheduler_service_account_email" {
  description = "Override the scheduler service account email."
  type        = string
  default     = null
}

variable "task_dispatcher_service_account_email" {
  description = "Override the task dispatcher invoker service account email."
  type        = string
  default     = null
}

variable "external_api_service_account_email" {
  description = "The service account email of an external API to grant invoker access to the OW API."
  type        = string
  default     = null
}

############################################
# Managed Services (SQL, Redis, GCS)
############################################

variable "create_cloud_sql" {
  description = "Whether to create/use a Cloud SQL instance."
  type        = bool
  default     = false
}

variable "cloud_sql_instance_name" {
  description = "Name of the Cloud SQL instance."
  type        = string
  default     = null
}

variable "cloud_sql_database_version" {
  description = "PostgreSQL version."
  type        = string
  default     = "POSTGRES_17"
}

variable "cloud_sql_db_name" {
  description = "Name of the PostgreSQL database."
  type        = string
  default     = "open_wearables"
}

variable "cloud_sql_db_user" {
  description = "PostgreSQL database user."
  type        = string
  default     = "open_wearables"
}

variable "cloud_sql_db_password" {
  description = "PostgreSQL database password."
  type        = string
  default     = null
}

variable "cloud_sql_deletion_protection" {
  description = "Whether deletion protection is enabled for the Cloud SQL instance."
  type        = bool
  default     = true
}

variable "cloud_sql_tier" {
  description = "The machine type for the Cloud SQL instance."
  type        = string
  default     = "db-f1-micro"
}

variable "cloud_sql_availability_type" {
  description = "The availability type for the Cloud SQL instance."
  type        = string
  default     = "ZONAL"
}

variable "cloud_sql_disk_size_gb" {
  description = "The disk size for the Cloud SQL instance in GB."
  type        = number
  default     = 10
}

variable "create_memorystore" {
  description = "Whether to create/use a Memorystore Redis instance."
  type        = bool
  default     = false
}

variable "memorystore_name" {
  description = "Name of the Memorystore Redis instance."
  type        = string
  default     = null
}

variable "memorystore_tier" {
  description = "The service tier of the Memorystore Redis instance."
  type        = string
  default     = "BASIC"
}

variable "memorystore_memory_size_gb" {
  description = "Redis memory size in GiB."
  type        = number
  default     = 1
}

variable "memorystore_version" {
  description = "The version of Redis."
  type        = string
  default     = "REDIS_7_0"
}

variable "create_task_payload_bucket" {
  description = "Whether to create a GCS bucket for large task payloads."
  type        = bool
  default     = true
}

variable "task_payload_bucket_name" {
  description = "Override name for the task payload bucket."
  type        = string
  default     = null
}

variable "enable_cloud_tasks_dispatch" {
  description = "Whether to enable Cloud Tasks for async execution."
  type        = bool
  default     = true
}

variable "create_default_scheduler_jobs" {
  description = "Whether to create default Cloud Scheduler maintenance jobs."
  type        = bool
  default     = true
}

variable "sync_all_users_schedule" {
  description = "Schedule for sync_all_users."
  type        = string
  default     = "0 * * * *"
}

variable "finalize_stale_sleeps_schedule" {
  description = "Schedule for finalize_stale_sleeps."
  type        = string
  default     = "30 * * * *"
}

variable "gc_stuck_backfills_schedule" {
  description = "Schedule for gc_stuck_backfills."
  type        = string
  default     = "0 2 * * *"
}

variable "scheduler_time_zone" {
  description = "Time zone for Cloud Scheduler jobs."
  type        = string
  default     = "Etc/UTC"
}
