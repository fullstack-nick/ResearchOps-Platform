resource "azurerm_cognitive_account" "document_intelligence" {
  name                  = "${local.combined}-docintel"
  resource_group_name   = azurerm_resource_group.main.name
  location              = azurerm_resource_group.main.location
  kind                  = "FormRecognizer"
  sku_name              = "F0"
  custom_subdomain_name = "${local.combined}-docintel"
  tags                  = local.tags
}

resource "azurerm_cognitive_account" "openai" {
  name                  = "${local.combined}-openai"
  resource_group_name   = azurerm_resource_group.main.name
  location              = azurerm_resource_group.main.location
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "${local.combined}-openai"
  tags                  = local.tags
}

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = "text-embedding-3-small"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.openai_embedding_model
    version = var.openai_embedding_model_version
  }

  sku {
    name     = "Standard"
    capacity = 50
  }
}

resource "azurerm_cognitive_deployment" "chat" {
  name                 = "gpt-4o-mini"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.openai_chat_model
    version = var.openai_chat_model_version
  }

  # Use GlobalStandard because the demo subscription has no quota for Standard
  # SKU chat models; GlobalStandard has plenty of tokens-per-minute.
  sku {
    name     = "GlobalStandard"
    capacity = 30
  }

  depends_on = [azurerm_cognitive_deployment.embedding]
}

resource "azurerm_search_service" "main" {
  name                = "${local.combined}-search"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "free"
  replica_count       = 1
  partition_count     = 1
  tags                = local.tags
}
