locals {
  network_name_resolved    = coalesce(var.network_name, "${local.resource_prefix}-network")
  subnetwork_name_resolved = coalesce(var.subnetwork_name, "${local.resource_prefix}-subnet")
  vpc_connector_name_resolved = coalesce(
    var.vpc_connector_name,
    "${local.resource_prefix}-connector",
  )
}

data "google_compute_network" "main" {
  count   = var.create_network ? 0 : (var.network_name != null ? 1 : 0)
  name    = var.network_name
  project = var.project_id
}

data "google_compute_subnetwork" "main" {
  count   = var.create_network ? 0 : (var.subnetwork_name != null ? 1 : 0)
  name    = var.subnetwork_name
  region  = var.region
  project = var.project_id
}

data "google_vpc_access_connector" "main" {
  count   = var.create_vpc_connector ? 0 : (var.vpc_connector_name != null ? 1 : 0)
  name    = var.vpc_connector_name
  region  = var.region
  project = var.project_id
}

locals {
  network_id = var.create_network ? google_compute_network.main[0].id : try(data.google_compute_network.main[0].id, null)
  subnetwork_name = var.create_network ? google_compute_subnetwork.main[0].name : try(data.google_compute_subnetwork.main[0].name, var.subnetwork_name)
  vpc_connector_id = var.create_vpc_connector ? google_vpc_access_connector.main[0].id : try(data.google_vpc_access_connector.main[0].id, var.vpc_connector_name != null ? "projects/${var.project_id}/locations/${var.region}/connectors/${var.vpc_connector_name}" : null)
}

resource "google_compute_network" "main" {
  count = var.create_network ? 1 : 0

  project                 = var.project_id
  name                    = local.network_name_resolved
  auto_create_subnetworks = false

  depends_on = [google_project_service.required]
}

resource "google_compute_subnetwork" "main" {
  count = var.create_network ? 1 : 0

  project                  = var.project_id
  name                     = local.subnetwork_name_resolved
  region                   = var.region
  ip_cidr_range            = var.subnet_cidr
  network                  = google_compute_network.main[0].id
  private_ip_google_access = true
}

resource "google_vpc_access_connector" "main" {
  count = var.create_vpc_connector && var.create_network ? 1 : 0

  project       = var.project_id
  name          = local.vpc_connector_name_resolved
  region        = var.region
  machine_type  = var.vpc_connector_machine_type
  min_instances = var.vpc_connector_min_instances
  max_instances = var.vpc_connector_max_instances

  network       = google_compute_network.main[0].id
  ip_cidr_range = "10.11.0.0/28"

  depends_on = [google_project_service.required]
}

resource "google_compute_global_address" "private_ip_address" {
  count = var.create_network ? 1 : 0

  project       = var.project_id
  name          = "${local.resource_prefix}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main[0].id

  depends_on = [google_project_service.required]
}

resource "google_service_networking_connection" "private_vpc_connection" {
  count = var.create_network ? 1 : 0

  network                 = google_compute_network.main[0].id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address[0].name]

  depends_on = [google_project_service.required]
}
