locals {
  resource_prefix = "${var.name_prefix}-${var.environment}"
}

resource "google_project_service" "required" {
  for_each = var.enable_apis ? toset(var.activate_apis) : toset([])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "containers" {
  count = var.create_artifact_registry ? 1 : 0

  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repository_id
  description   = var.artifact_registry_description
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

resource "google_service_account" "accounts" {
  for_each = var.create_service_accounts ? var.service_accounts : {}

  project      = var.project_id
  account_id   = substr(replace("${local.resource_prefix}-${each.key}", "_", "-"), 0, 30)
  display_name = each.value.display_name
  description  = each.value.description

  depends_on = [google_project_service.required]
}

resource "google_cloud_tasks_queue" "queues" {
  for_each = var.queue_configs

  project  = var.project_id
  location = var.region
  name     = "${local.resource_prefix}-${replace(each.key, "_", "-")}"

  rate_limits {
    max_dispatches_per_second = each.value.max_dispatches_per_second
    max_concurrent_dispatches = each.value.max_concurrent_dispatches
  }

  retry_config {
    max_attempts = each.value.max_attempts
    min_backoff  = each.value.min_backoff
    max_backoff  = each.value.max_backoff
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "secrets" {
  for_each = var.create_secrets ? toset(var.secret_names) : toset([])

  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "versions" {
  for_each = var.create_secrets ? var.secret_values : {}

  secret      = google_secret_manager_secret.secrets[each.key].id
  secret_data = each.value

  depends_on = [google_secret_manager_secret.secrets]
}

resource "google_cloud_scheduler_job" "jobs" {
  for_each = var.scheduler_jobs

  project     = var.project_id
  region      = var.region
  name        = "${local.resource_prefix}-${each.key}"
  description = each.value.description
  schedule    = each.value.schedule
  time_zone   = each.value.time_zone

  http_target {
    uri         = each.value.target_url
    http_method = each.value.http_method
    headers     = each.value.headers
    body        = try(base64encode(each.value.body), null)

    oidc_token {
      service_account_email = each.value.oidc_service_account_email
      audience              = try(each.value.audience, null)
    }
  }

  depends_on = [google_project_service.required]
}
