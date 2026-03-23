output "backend_api_url" {
  description = "The URL of the API service."
  value       = module.open_wearables_stack.backend_api_url
}

output "worker_url" {
  description = "The URL of the Worker service."
  value       = module.open_wearables_stack.backend_worker_url
}

output "frontend_url" {
  description = "The URL of the Frontend service."
  value       = module.open_wearables_stack.frontend_url
}

output "artifact_registry_repository_url" {
  value = module.open_wearables_stack.artifact_registry_repository_url
}

output "frontend_dns_records" {
  description = "DNS records for the custom domain."
  value       = module.open_wearables_stack.frontend_domain_mapping_records
}
