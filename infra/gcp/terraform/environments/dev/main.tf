module "open_wearables_stack" {
  source = "../../modules/open_wearables_stack"

  project_id                      = var.project_id
  region                          = var.region
  environment                     = "dev"
  name_prefix                     = var.name_prefix
  labels                          = var.labels
  artifact_registry_repository_id = var.artifact_registry_repository_id
  create_secrets                  = var.create_secrets
  secret_names                    = var.secret_names
  github_owner                    = var.github_owner
  github_repository_name          = var.github_repository_name
  branch_pattern                  = var.branch_pattern
  scheduler_jobs                  = var.scheduler_jobs

  # Shared Infrastructure Integration
  create_network        = var.create_network
  network_name          = var.network_name
  subnetwork_name       = "ow-srvless-subnet"
  vpc_connector_name    = "ow-srvless-connector"

  create_cloud_sql        = false # Set to true to create a new Cloud SQL instance
  cloud_sql_instance_name = "ow-postgres"
  cloud_sql_db_name       = var.cloud_sql_db_name
  cloud_sql_db_user       = var.cloud_sql_db_user
  cloud_sql_db_password   = var.cloud_sql_db_password

  create_memorystore    = false # Set to true to create a new Redis instance
  memorystore_name      = "ow-redis"

  # Service Configuration
  enable_backend_api_service    = var.enable_backend_api_service
  enable_worker_service         = var.enable_worker_service
  enable_backend_init_job       = var.enable_backend_init_job
  enable_frontend_service       = var.enable_frontend_service
  enable_cloud_tasks_dispatch   = var.enable_cloud_tasks_dispatch
  create_default_scheduler_jobs = var.create_default_scheduler_jobs

  external_api_service_account_email = var.external_api_service_account_email

  worker_service_base_url       = var.worker_service_base_url
  backend_image                 = var.backend_image
  frontend_image                = var.frontend_image

  backend_api_env               = var.backend_api_env
  backend_worker_env            = var.backend_worker_env
  backend_init_env              = var.backend_init_env
  frontend_env                  = var.frontend_env

  backend_api_secret_env        = var.backend_api_secret_env
  backend_worker_secret_env     = var.backend_worker_secret_env
  backend_init_secret_env       = var.backend_init_secret_env
  frontend_secret_env           = var.frontend_secret_env
}
