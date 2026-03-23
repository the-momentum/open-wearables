locals {
  cloud_sql_instance_name_resolved = coalesce(var.cloud_sql_instance_name, "${local.resource_prefix}-db")
  memorystore_name_resolved        = coalesce(var.memorystore_name, "${local.resource_prefix}-redis")
}

data "google_sql_database_instance" "main" {
  count   = var.create_cloud_sql ? 0 : (var.cloud_sql_instance_name != null ? 1 : 0)
  name    = var.cloud_sql_instance_name
  project = var.project_id
}

data "google_redis_instance" "main" {
  count   = var.create_memorystore ? 0 : (var.memorystore_name != null ? 1 : 0)
  name    = var.memorystore_name
  region  = var.region
  project = var.project_id
}

locals {
  cloud_sql_instance_name = var.create_cloud_sql ? google_sql_database_instance.main[0].name : (var.cloud_sql_instance_name != null ? data.google_sql_database_instance.main[0].name : null)
  cloud_sql_connection_name = var.create_cloud_sql ? google_sql_database_instance.main[0].connection_name : (var.cloud_sql_instance_name != null ? data.google_sql_database_instance.main[0].connection_name : null)
  redis_host = var.create_memorystore ? google_redis_instance.main[0].host : (var.memorystore_name != null ? data.google_redis_instance.main[0].host : null)
  redis_port = var.create_memorystore ? google_redis_instance.main[0].port : (var.memorystore_name != null ? data.google_redis_instance.main[0].port : 6379)
}

resource "google_sql_database_instance" "main" {
  count = var.create_cloud_sql ? 1 : 0

  project             = var.project_id
  name                = local.cloud_sql_instance_name_resolved
  region              = var.region
  database_version    = var.cloud_sql_database_version
  deletion_protection = var.cloud_sql_deletion_protection

  settings {
    tier              = var.cloud_sql_tier
    edition           = "ENTERPRISE"
    availability_type = var.cloud_sql_availability_type
    disk_size         = var.cloud_sql_disk_size_gb
    disk_type         = "PD_SSD"

    ip_configuration {
      ipv4_enabled = true
    }

    backup_configuration {
      enabled = true
    }
  }

  lifecycle {
    precondition {
      condition     = var.cloud_sql_db_password != null
      error_message = "cloud_sql_db_password must be set when create_cloud_sql is true."
    }
  }

  depends_on = [
    google_project_service.required,
    google_service_networking_connection.private_vpc_connection
  ]
}

resource "google_sql_database" "app" {
  # Create a database if we are creating the instance OR if an instance name is provided but we don't create it
  count = (var.create_cloud_sql || var.cloud_sql_instance_name != null) ? 1 : 0

  project  = var.project_id
  name     = var.cloud_sql_db_name
  instance = local.cloud_sql_instance_name
}

resource "google_sql_user" "app" {
  count = (var.create_cloud_sql || var.cloud_sql_instance_name != null) ? 1 : 0

  project  = var.project_id
  instance = local.cloud_sql_instance_name
  name     = var.cloud_sql_db_user
  password = var.cloud_sql_db_password
}

resource "google_redis_instance" "main" {
  count = var.create_memorystore ? 1 : 0

  project            = var.project_id
  region             = var.region
  name               = local.memorystore_name_resolved
  tier               = var.memorystore_tier
  memory_size_gb     = var.memorystore_memory_size_gb
  redis_version      = var.memorystore_version
  connect_mode       = "PRIVATE_SERVICE_ACCESS"
  authorized_network = local.network_id

  lifecycle {
    precondition {
      condition     = local.network_id != null
      error_message = "A network ID must be available (created or provided) when create_memorystore is true."
    }
  }

  depends_on = [
    google_project_service.required,
    google_service_networking_connection.private_vpc_connection
  ]
}

resource "google_storage_bucket" "task_payloads" {
  count = var.enable_cloud_tasks_dispatch ? 1 : 0

  project                     = var.project_id
  name                        = "${local.resource_prefix}-task-payloads"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 7 # Delete objects older than 7 days
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required]
}

