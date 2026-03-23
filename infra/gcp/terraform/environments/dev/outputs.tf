output "artifact_registry_repository_url" {
  description = "Artifact Registry docker repository path."
  value       = module.open_wearables_stack.artifact_registry_repository_url
}

output "service_account_emails" {
  description = "Service account emails by logical role."
  value       = module.open_wearables_stack.service_account_emails
}

output "task_queue_names" {
  description = "Cloud Tasks queue names."
  value       = module.open_wearables_stack.task_queue_names
}

output "scheduler_job_names" {
  description = "Cloud Scheduler job names."
  value       = module.open_wearables_stack.scheduler_job_names
}

output "backend_api_url" {
  description = "Backend API URL."
  value       = module.open_wearables_stack.backend_api_url
}

output "backend_worker_url" {
  description = "Worker service URL."
  value       = module.open_wearables_stack.backend_worker_url
}

output "frontend_url" {
  description = "Frontend URL."
  value       = module.open_wearables_stack.frontend_url
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name."
  value       = module.open_wearables_stack.cloud_sql_connection_name
}

output "redis_host" {
  description = "Redis host."
  value       = module.open_wearables_stack.redis_host
}
