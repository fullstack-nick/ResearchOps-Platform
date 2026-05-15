resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
  numeric = true
  lower   = true
}

resource "random_password" "postgres" {
  length           = 32
  special          = true
  min_special      = 2
  min_lower        = 4
  min_upper        = 4
  min_numeric      = 4
  override_special = "_-"
}

resource "random_password" "mcp_dev_token" {
  length  = 40
  special = false
}

locals {
  name_prefix   = var.prefix
  suffix        = random_string.suffix.result
  combined      = "${local.name_prefix}-${local.suffix}"
  combined_flat = "${local.name_prefix}${local.suffix}"
  tags          = merge(var.common_tags, { environment = var.environment })
}

resource "azurerm_resource_group" "main" {
  name     = "${local.combined}-rg"
  location = var.location
  tags     = local.tags
}
