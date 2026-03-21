resource "google_cloudbuild_trigger" "backend" {
  count = var.enable_cloud_build_triggers && var.enable_backend_api_service ? 1 : 0

  project     = var.project_id
  name        = "${local.resource_prefix}-backend"
  description = "Build and deploy backend to Cloud Run"

  github {
    owner = var.github_owner
    name  = var.github_repository_name
    push {
      branch = var.branch_pattern
    }
  }

  filename = "backend/cloudbuild.yaml"

  substitutions = {
    _REGION         = var.region
    _REPOSITORY     = google_artifact_registry_repository.containers[0].name
    _IMAGE_NAME     = "backend"
    _API_SERVICE    = local.backend_api_service_name_resolved
    _WORKER_SERVICE = local.backend_worker_service_name_resolved
    _INIT_JOB       = local.backend_init_job_name_resolved
  }

  depends_on = [google_artifact_registry_repository.containers]
}

resource "google_cloudbuild_trigger" "frontend" {
  count = var.enable_cloud_build_triggers && var.enable_frontend_service ? 1 : 0

  project     = var.project_id
  name        = "${local.resource_prefix}-frontend"
  description = "Build and deploy frontend to Cloud Run"

  github {
    owner = var.github_owner
    name  = var.github_repository_name
    push {
      branch = var.branch_pattern
    }
  }

  filename = "frontend/cloudbuild.yaml"

  substitutions = {
    _REGION       = var.region
    _REPOSITORY   = google_artifact_registry_repository.containers[0].name
    _IMAGE_NAME   = "frontend"
    _SERVICE_NAME = local.frontend_service_name_resolved
  }

  depends_on = [google_artifact_registry_repository.containers]
}
