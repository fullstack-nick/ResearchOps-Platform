output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "location" {
  value = azurerm_resource_group.main.location
}

output "container_registry_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "container_registry_name" {
  value = azurerm_container_registry.main.name
}

output "container_app_environment_id" {
  value = azurerm_container_app_environment.main.id
}

output "container_app_environment_domain" {
  value = azurerm_container_app_environment.main.default_domain
}

output "frontend_url" {
  value = local.frontend_url
}

output "backend_url" {
  value = local.backend_url
}

output "mcp_url" {
  value = local.mcp_url
}

output "postgres_fqdn" {
  value = local.postgres_fqdn
}

output "postgres_database" {
  value = azurerm_postgresql_flexible_server_database.researchops.name
}

output "postgres_admin_user" {
  value = var.postgres_admin_user
}

output "postgres_admin_password" {
  value     = random_password.postgres.result
  sensitive = true
}

output "storage_account_name" {
  value = azurerm_storage_account.main.name
}

output "storage_container_name" {
  value = azurerm_storage_container.documents.name
}

output "document_intelligence_endpoint" {
  value = azurerm_cognitive_account.document_intelligence.endpoint
}

output "openai_endpoint" {
  value = azurerm_cognitive_account.openai.endpoint
}

output "openai_embedding_deployment" {
  value = azurerm_cognitive_deployment.embedding.name
}

output "openai_chat_deployment" {
  value = azurerm_cognitive_deployment.chat.name
}

output "search_endpoint" {
  value = "https://${azurerm_search_service.main.name}.search.windows.net"
}

output "search_admin_key" {
  value     = azurerm_search_service.main.primary_key
  sensitive = true
}

output "mcp_dev_token" {
  value     = random_password.mcp_dev_token.result
  sensitive = true
}

output "application_insights_connection_string" {
  value     = azurerm_application_insights.main.connection_string
  sensitive = true
}

output "grafana_endpoint" {
  value = azurerm_dashboard_grafana.main.endpoint
}

output "grafana_name" {
  value = azurerm_dashboard_grafana.main.name
}

output "user_assigned_identity_id" {
  value = azurerm_user_assigned_identity.apps.id
}

output "user_assigned_identity_client_id" {
  value = azurerm_user_assigned_identity.apps.client_id
}
