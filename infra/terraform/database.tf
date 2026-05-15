resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "${local.combined}-db"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = var.postgres_location
  version                       = "16"
  sku_name                      = "B_Standard_B1ms"
  storage_mb                    = 32768
  storage_tier                  = "P4"
  backup_retention_days         = 7
  geo_redundant_backup_enabled  = false
  administrator_login           = var.postgres_admin_user
  administrator_password        = random_password.postgres.result
  public_network_access_enabled = true
  zone                          = "1"
  tags                          = local.tags
}

resource "azurerm_postgresql_flexible_server_database" "researchops" {
  name      = "researchops"
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "UTF8"
}

# Allow Azure services (including Container Apps) plus broad public access for
# operator-driven Alembic migrations. The demo subscription has no private
# networking, so we open the firewall and rely on Entra ID + RBAC for access
# control in the application layer.
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  name             = "AllowAllAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_public" {
  name             = "AllowPublicForMigrations"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "255.255.255.255"
}
