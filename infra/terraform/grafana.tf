locals {
  grafana_admin_principal_object_ids = toset(concat(
    [data.azurerm_client_config.current.object_id],
    var.grafana_admin_principal_object_ids,
  ))
}

resource "azurerm_dashboard_grafana" "main" {
  name                          = "${local.combined}-gfn"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  grafana_major_version         = "12"
  sku                           = "Standard"
  api_key_enabled               = false
  public_network_access_enabled = true
  zone_redundancy_enabled       = false
  tags                          = merge(local.tags, { phase = "phase-7-observability" })

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "grafana_monitoring_reader_rg" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Monitoring Reader"
  principal_id         = azurerm_dashboard_grafana.main.identity[0].principal_id
}

resource "azurerm_role_assignment" "grafana_log_analytics_reader" {
  scope                = azurerm_log_analytics_workspace.main.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = azurerm_dashboard_grafana.main.identity[0].principal_id
}

resource "azurerm_role_assignment" "grafana_admins" {
  for_each             = local.grafana_admin_principal_object_ids
  scope                = azurerm_dashboard_grafana.main.id
  role_definition_name = "Grafana Admin"
  principal_id         = each.value
}
