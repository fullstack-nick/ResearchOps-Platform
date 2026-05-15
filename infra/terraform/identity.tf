resource "azurerm_user_assigned_identity" "apps" {
  name                = "${local.combined}-apps-id"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.tags
}
