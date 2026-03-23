output "artifact_registry_repository" {
  description = "Created Artifact Registry repository."
  value       = var.create_artifact_registry ? one(google_artifact_registry_repository.containers[*].id) : null
}

output "artifact_registry_repository_url" {
  description = "Docker repository hostname path."
  value       = var.create_artifact_registry ? "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository_id}" : null
}

output "service_account_emails" {
  description = "Service account emails by logical name."
  value       = { for key, account in google_service_account.accounts : key => account.email }
}

output "task_queue_names" {
  description = "Cloud Tasks queue names by logical queue key."
  value       = { for key, queue in google_cloud_tasks_queue.queues : key => queue.name }
}

output "secret_ids" {
  description = "Secret Manager secret IDs."
  value       = { for key, secret in google_secret_manager_secret.secrets : key => secret.secret_id }
}

output "scheduler_job_names" {
  description = "Cloud Scheduler job names."
  value       = { for key, job in google_cloud_scheduler_job.jobs : key => job.name }
}

output "frontend_domain_mapping_records" {
  description = "DNS records for the frontend domain mapping."
  value       = var.enable_frontend_service && var.frontend_custom_domain != null ? google_cloud_run_domain_mapping.frontend[0].status[0].resource_records : []
}
