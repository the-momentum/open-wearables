locals {
  service_account_role_pairs = flatten([
    for account_key, roles in var.service_account_project_roles : [
      for role in roles : {
        key         = "${account_key}-${replace(role, "/", "_")}"
        account_key = account_key
        role        = role
      }
    ]
  ])
}

resource "google_project_iam_member" "service_account_roles" {
  for_each = var.create_service_accounts ? { for pair in local.service_account_role_pairs : pair.key => pair } : {}

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.accounts[each.value.account_key].email}"
}
