output "network_name" {
  description = "Created VPC network name."
  value       = length(google_compute_network.main) > 0 ? one(google_compute_network.main[*].name) : null
}

output "vpc_connector_id" {
  description = "Serverless VPC Access connector ID."
  value       = length(google_vpc_access_connector.main) > 0 ? one(google_vpc_access_connector.main[*].id) : null
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name."
  value       = length(google_sql_database_instance.main) > 0 ? one(google_sql_database_instance.main[*].connection_name) : null
}

output "cloud_sql_instance_name" {
  description = "Cloud SQL instance name."
  value       = length(google_sql_database_instance.main) > 0 ? one(google_sql_database_instance.main[*].name) : null
}

output "redis_host" {
  description = "Memorystore Redis host."
  value       = length(google_redis_instance.main) > 0 ? one(google_redis_instance.main[*].host) : null
}

output "redis_port" {
  description = "Memorystore Redis port."
  value       = length(google_redis_instance.main) > 0 ? one(google_redis_instance.main[*].port) : null
}

output "backend_api_url" {
  description = "Backend API Cloud Run URL."
  value       = length(google_cloud_run_v2_service.backend_api) > 0 ? one(google_cloud_run_v2_service.backend_api[*].uri) : null
}

output "backend_worker_url" {
  description = "Worker Cloud Run URL."
  value       = length(google_cloud_run_v2_service.backend_worker) > 0 ? one(google_cloud_run_v2_service.backend_worker[*].uri) : null
}

output "frontend_url" {
  description = "Frontend Cloud Run URL."
  value       = length(google_cloud_run_v2_service.frontend) > 0 ? one(google_cloud_run_v2_service.frontend[*].uri) : null
}

output "backend_init_job_name" {
  description = "Backend init Cloud Run Job name."
  value       = length(google_cloud_run_v2_job.backend_init) > 0 ? one(google_cloud_run_v2_job.backend_init[*].name) : null
}
