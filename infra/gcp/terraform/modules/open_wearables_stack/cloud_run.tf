locals {
  api_service_account_email = coalesce(
    var.api_service_account_email,
    try(google_service_account.accounts["api"].email, null),
  )
  worker_service_account_email = coalesce(
    var.worker_service_account_email,
    try(google_service_account.accounts["worker"].email, null),
  )
  migrator_service_account_email = coalesce(
    var.migrator_service_account_email,
    try(google_service_account.accounts["migrator"].email, null),
  )
  frontend_service_account_email = coalesce(
    var.frontend_service_account_email,
    try(google_service_account.accounts["api"].email, null),
  )
  scheduler_service_account_email = coalesce(
    var.scheduler_service_account_email,
    try(google_service_account.accounts["scheduler"].email, null),
  )
  task_dispatch_invoker_service_account_email = coalesce(
    var.task_dispatcher_service_account_email,
    local.api_service_account_email,
  )

  backend_api_service_name_resolved    = coalesce(var.backend_api_service_name, "${local.resource_prefix}-api")
  backend_worker_service_name_resolved = coalesce(var.backend_worker_service_name, "${local.resource_prefix}-worker")
  backend_init_job_name_resolved       = coalesce(var.backend_init_job_name, "${local.resource_prefix}-init")
  frontend_service_name_resolved       = coalesce(var.frontend_service_name, "${local.resource_prefix}-frontend")

  backend_runtime_env = merge(
    local.cloud_sql_connection_name != null ? merge(
      {
        DB_NAME        = var.cloud_sql_db_name
        DB_USER        = var.cloud_sql_db_user
        DB_SOCKET_PATH = "/cloudsql/${local.cloud_sql_connection_name}"
      },
      var.cloud_sql_db_password != null ? { DB_PASSWORD = var.cloud_sql_db_password } : {}
    ) : {},
    local.redis_host != null ? {
      REDIS_HOST = local.redis_host
      REDIS_PORT = tostring(local.redis_port)
    } : {},
  )

  dispatcher_runtime_env = var.enable_cloud_tasks_dispatch ? {
    TASK_DISPATCH_BACKEND                      = "cloud_tasks"
    TASK_DISPATCHER_GCP_PROJECT_ID             = var.project_id
    TASK_DISPATCHER_GCP_LOCATION               = var.region
    TASK_DISPATCHER_WORKER_BASE_URL            = coalesce(var.worker_service_base_url, "")
    TASK_DISPATCHER_SERVICE_ACCOUNT_EMAIL      = coalesce(local.task_dispatch_invoker_service_account_email, "")
    TASK_DISPATCHER_AUDIENCE                   = coalesce(var.worker_service_base_url, "")
    TASK_DISPATCHER_DEFAULT_QUEUE_NAME         = google_cloud_tasks_queue.queues["default"].name
    TASK_DISPATCHER_SDK_SYNC_QUEUE_NAME        = google_cloud_tasks_queue.queues["sdk_sync"].name
    TASK_DISPATCHER_GARMIN_BACKFILL_QUEUE_NAME = google_cloud_tasks_queue.queues["garmin_backfill"].name
    TASK_PAYLOAD_STORAGE_BACKEND               = "gcs"
    TASK_PAYLOAD_GCS_BUCKET                    = google_storage_bucket.task_payloads[0].name
  } : {}

  backend_api_env_resolved = merge(
    var.backend_api_env,
    local.backend_runtime_env,
    local.dispatcher_runtime_env,
  )
  backend_worker_env_resolved = merge(
    var.backend_worker_env,
    local.backend_runtime_env,
    local.dispatcher_runtime_env,
    {
      INTERNAL_TASK_API_ENABLED = "true"
    },
  )
  backend_init_env_resolved = merge(
    var.backend_init_env,
    local.backend_runtime_env,
  )

  worker_invoker_members = toset(compact([
    var.enable_cloud_tasks_dispatch ? local.task_dispatch_invoker_service_account_email : null,
    var.create_default_scheduler_jobs ? local.scheduler_service_account_email : null,
  ]))
}

resource "google_cloud_run_v2_service" "backend_api" {
  count = var.enable_backend_api_service ? 1 : 0

  project  = var.project_id
  name     = local.backend_api_service_name_resolved
  location = var.region
  ingress  = var.backend_api_ingress
  deletion_protection = false

  labels = merge(var.labels, { component = "backend-api" })

  template {
    service_account                  = local.api_service_account_email
    timeout                          = "${var.backend_api_timeout_seconds}s"
    max_instance_request_concurrency = var.backend_api_concurrency

    scaling {
      min_instance_count = var.backend_api_min_instances
      max_instance_count = var.backend_api_max_instances
    }

    dynamic "volumes" {
      for_each = local.cloud_sql_connection_name != null ? [1] : []
      content {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [local.cloud_sql_connection_name]
        }
      }
    }

    dynamic "vpc_access" {
      for_each = local.vpc_connector_id != null ? [1] : []
      content {
        connector = local.vpc_connector_id
        egress    = var.backend_vpc_egress
      }
    }

    containers {
      image   = var.backend_image
      command = var.backend_api_command
      args    = var.backend_api_args

      ports {
        container_port = var.backend_container_port
      }

      resources {
        limits = var.backend_api_resource_limits
      }

      dynamic "env" {
        for_each = local.backend_api_env_resolved
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.backend_api_secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret
              version = try(env.value.version, "latest")
            }
          }
        }
      }

      dynamic "volume_mounts" {
        for_each = local.cloud_sql_connection_name != null ? [1] : []
        content {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = var.backend_image != null
      error_message = "backend_image must be set when enable_backend_api_service is true."
    }
    precondition {
      condition     = !var.enable_cloud_tasks_dispatch || var.worker_service_base_url != null
      error_message = "worker_service_base_url must be set when enable_cloud_tasks_dispatch is true."
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service" "backend_worker" {
  count = var.enable_worker_service ? 1 : 0

  project  = var.project_id
  name     = local.backend_worker_service_name_resolved
  location = var.region
  ingress  = var.backend_worker_ingress
  deletion_protection = false

  labels = merge(var.labels, { component = "backend-worker" })

  template {
    service_account                  = local.worker_service_account_email
    timeout                          = "${var.backend_worker_timeout_seconds}s"
    max_instance_request_concurrency = var.backend_worker_concurrency

    scaling {
      min_instance_count = var.backend_worker_min_instances
      max_instance_count = var.backend_worker_max_instances
    }

    dynamic "volumes" {
      for_each = local.cloud_sql_connection_name != null ? [1] : []
      content {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [local.cloud_sql_connection_name]
        }
      }
    }

    dynamic "vpc_access" {
      for_each = local.vpc_connector_id != null ? [1] : []
      content {
        connector = local.vpc_connector_id
        egress    = var.backend_vpc_egress
      }
    }

    containers {
      image   = var.backend_image
      command = var.backend_worker_command
      args    = var.backend_worker_args

      ports {
        container_port = var.backend_container_port
      }

      resources {
        limits = var.backend_worker_resource_limits
      }

      dynamic "env" {
        for_each = local.backend_worker_env_resolved
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.backend_worker_secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret
              version = try(env.value.version, "latest")
            }
          }
        }
      }

      dynamic "volume_mounts" {
        for_each = local.cloud_sql_connection_name != null ? [1] : []
        content {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = var.backend_image != null
      error_message = "backend_image must be set when enable_worker_service is true."
    }
    precondition {
      condition     = !var.enable_cloud_tasks_dispatch || var.worker_service_base_url != null
      error_message = "worker_service_base_url must be set when enable_cloud_tasks_dispatch is true."
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_job" "backend_init" {
  count = var.enable_backend_init_job ? 1 : 0

  project  = var.project_id
  name     = local.backend_init_job_name_resolved
  location = var.region
  deletion_protection = false
  labels   = merge(var.labels, { component = "backend-init" })

  template {
    template {
      service_account = local.migrator_service_account_email
      timeout         = "${var.backend_init_timeout_seconds}s"
      max_retries     = 1

      dynamic "volumes" {
        for_each = local.cloud_sql_connection_name != null ? [1] : []
        content {
          name = "cloudsql"
          cloud_sql_instance {
            instances = [local.cloud_sql_connection_name]
          }
        }
      }

      dynamic "vpc_access" {
        for_each = local.vpc_connector_id != null ? [1] : []
        content {
          connector = local.vpc_connector_id
          egress    = var.backend_vpc_egress
        }
      }

      containers {
        image   = var.backend_image
        command = var.backend_init_command
        args    = var.backend_init_args

        resources {
          limits = var.backend_init_resource_limits
        }

        dynamic "env" {
          for_each = local.backend_init_env_resolved
          content {
            name  = env.key
            value = env.value
          }
        }

        dynamic "env" {
          for_each = var.backend_init_secret_env
          content {
            name = env.key
            value_source {
              secret_key_ref {
                secret  = env.value.secret
                version = try(env.value.version, "latest")
              }
            }
          }
        }

        dynamic "volume_mounts" {
          for_each = local.cloud_sql_connection_name != null ? [1] : []
          content {
            name       = "cloudsql"
            mount_path = "/cloudsql"
          }
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = var.backend_image != null
      error_message = "backend_image must be set when enable_backend_init_job is true."
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service" "frontend" {
  count = var.enable_frontend_service ? 1 : 0

  project  = var.project_id
  name     = local.frontend_service_name_resolved
  location = var.region
  ingress  = var.frontend_ingress
  deletion_protection = false

  labels = merge(var.labels, { component = "frontend" })

  template {
    service_account                  = local.frontend_service_account_email
    timeout                          = "${var.frontend_timeout_seconds}s"
    max_instance_request_concurrency = var.frontend_concurrency

    scaling {
      min_instance_count = var.frontend_min_instances
      max_instance_count = var.frontend_max_instances
    }

    containers {
      image   = var.frontend_image
      command = var.frontend_command
      args    = var.frontend_args

      ports {
        container_port = var.frontend_container_port
      }

      resources {
        limits = var.frontend_resource_limits
      }

      dynamic "env" {
        for_each = var.frontend_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.frontend_secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret
              version = try(env.value.version, "latest")
            }
          }
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = var.frontend_image != null
      error_message = "frontend_image must be set when enable_frontend_service is true."
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service_iam_member" "backend_api_external_invoker" {
  count = var.enable_backend_api_service && var.external_api_service_account_email != null ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend_api[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.external_api_service_account_email}"
}

resource "google_cloud_run_v2_service_iam_member" "backend_api_public_invoker" {
  count = var.enable_backend_api_service && var.backend_api_allow_unauthenticated ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend_api[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "frontend_public_invoker" {
  count = var.enable_frontend_service && var.frontend_allow_unauthenticated ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "worker_invokers" {
  for_each = var.enable_worker_service ? local.worker_invoker_members : toset([])

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend_worker[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${each.value}"
}

resource "google_cloud_scheduler_job" "default_jobs" {
  for_each = var.create_default_scheduler_jobs && var.enable_worker_service ? {
    sync_all_users = {
      description = "Run periodic vendor sync fan-out"
      schedule    = var.sync_all_users_schedule
      path        = "/internal/tasks/sync_all_users"
    }
    finalize_stale_sleeps = {
      description = "Finalize stale sleep sessions"
      schedule    = var.finalize_stale_sleeps_schedule
      path        = "/internal/tasks/finalize_stale_sleeps"
    }
    gc_stuck_backfills = {
      description = "Garmin backfill GC"
      schedule    = var.gc_stuck_backfills_schedule
      path        = "/internal/tasks/gc_stuck_backfills"
    }
  } : {}

  project     = var.project_id
  region      = var.region
  name        = "${local.resource_prefix}-${replace(each.key, "_", "-")}"
  description = each.value.description
  schedule    = each.value.schedule
  time_zone   = var.scheduler_time_zone

  http_target {
    uri         = "${google_cloud_run_v2_service.backend_worker[0].uri}/api/v1${each.value.path}"
    http_method = "POST"

    oidc_token {
      service_account_email = local.scheduler_service_account_email
      audience              = google_cloud_run_v2_service.backend_worker[0].uri
    }
  }

  depends_on = [google_cloud_run_v2_service.backend_worker]
}

resource "google_cloud_run_domain_mapping" "frontend" {
  count = var.enable_frontend_service && var.frontend_custom_domain != null ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = var.frontend_custom_domain

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.frontend[0].name
  }
}
