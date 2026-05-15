resource "azurerm_container_app_environment" "main" {
  name                       = "${local.combined}-aca-env"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = local.tags
}

locals {
  postgres_fqdn = azurerm_postgresql_flexible_server.main.fqdn
  database_url = format(
    "postgresql+asyncpg://%s:%s@%s:5432/%s?ssl=require",
    var.postgres_admin_user,
    random_password.postgres.result,
    azurerm_postgresql_flexible_server.main.fqdn,
    azurerm_postgresql_flexible_server_database.researchops.name,
  )
  storage_account_url       = azurerm_storage_account.main.primary_blob_endpoint
  backend_fqdn              = "${local.combined}-backend.${azurerm_container_app_environment.main.default_domain}"
  frontend_fqdn             = "${local.combined}-frontend.${azurerm_container_app_environment.main.default_domain}"
  mcp_fqdn                  = "${local.combined}-mcp.${azurerm_container_app_environment.main.default_domain}"
  backend_url               = "https://${local.backend_fqdn}"
  frontend_url              = "https://${local.frontend_fqdn}"
  mcp_url                   = "https://${local.mcp_fqdn}"
  azure_storage_account_url = "https://${azurerm_storage_account.main.name}.blob.core.windows.net"
  shared_secrets = {
    db_url                    = local.database_url
    storage_connection_string = azurerm_storage_account.main.primary_connection_string
    docintel_endpoint         = azurerm_cognitive_account.document_intelligence.endpoint
    docintel_key              = azurerm_cognitive_account.document_intelligence.primary_access_key
    openai_endpoint           = azurerm_cognitive_account.openai.endpoint
    openai_key                = azurerm_cognitive_account.openai.primary_access_key
    search_endpoint           = "https://${azurerm_search_service.main.name}.search.windows.net"
    search_admin_key          = azurerm_search_service.main.primary_key
    app_insights_conn_string  = azurerm_application_insights.main.connection_string
    mcp_dev_token             = random_password.mcp_dev_token.result
  }
}

resource "azurerm_container_app" "backend" {
  name                         = "${local.combined}-backend"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  ingress {
    external_enabled           = true
    target_port                = 8000
    transport                  = "auto"
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  secret {
    name  = "database-url"
    value = local.shared_secrets.db_url
  }
  secret {
    name  = "storage-connection-string"
    value = local.shared_secrets.storage_connection_string
  }
  secret {
    name  = "docintel-key"
    value = local.shared_secrets.docintel_key
  }
  secret {
    name  = "openai-key"
    value = local.shared_secrets.openai_key
  }
  secret {
    name  = "search-admin-key"
    value = local.shared_secrets.search_admin_key
  }
  secret {
    name  = "app-insights-conn"
    value = local.shared_secrets.app_insights_conn_string
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name   = "backend"
      image  = var.backend_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name  = "FRONTEND_ORIGIN"
        value = local.frontend_url
      }
      env {
        name  = "STORAGE_DIR"
        value = "/app/storage/uploads"
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER"
        value = azurerm_storage_container.documents.name
      }
      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "storage-connection-string"
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_URL"
        value = local.azure_storage_account_url
      }
      env {
        name  = "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
        value = local.shared_secrets.docintel_endpoint
      }
      env {
        name        = "AZURE_DOCUMENT_INTELLIGENCE_KEY"
        secret_name = "docintel-key"
      }
      env {
        name  = "AZURE_SEARCH_ENDPOINT"
        value = local.shared_secrets.search_endpoint
      }
      env {
        name        = "AZURE_SEARCH_API_KEY"
        secret_name = "search-admin-key"
      }
      env {
        name  = "AZURE_SEARCH_INDEX_NAME"
        value = "researchops-document-chunks"
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = local.shared_secrets.openai_endpoint
      }
      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "openai-key"
      }
      env {
        name  = "AZURE_OPENAI_API_VERSION"
        value = "2024-10-21"
      }
      env {
        name  = "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        value = azurerm_cognitive_deployment.embedding.name
      }
      env {
        name  = "AZURE_OPENAI_EMBEDDING_DIMENSIONS"
        value = "1536"
      }
      env {
        name  = "AZURE_OPENAI_CHAT_DEPLOYMENT"
        value = azurerm_cognitive_deployment.chat.name
      }
      env {
        name  = "AUTH_MODE"
        value = "development"
      }
      env {
        name  = "DEV_DEFAULT_USER_EMAIL"
        value = "demo.researchops@example.test"
      }
      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "app-insights-conn"
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.apps_acr_pull,
    azurerm_postgresql_flexible_server_database.researchops,
    azurerm_cognitive_deployment.chat,
  ]
}

resource "azurerm_container_app" "worker" {
  name                         = "${local.combined}-worker"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  secret {
    name  = "database-url"
    value = local.shared_secrets.db_url
  }
  secret {
    name  = "storage-connection-string"
    value = local.shared_secrets.storage_connection_string
  }
  secret {
    name  = "docintel-key"
    value = local.shared_secrets.docintel_key
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name    = "worker"
      image   = var.worker_image
      cpu     = 0.5
      memory  = "1Gi"
      command = ["python", "-m", "app.extraction.worker"]

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name  = "STORAGE_DIR"
        value = "/app/storage/uploads"
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER"
        value = azurerm_storage_container.documents.name
      }
      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "storage-connection-string"
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_URL"
        value = local.azure_storage_account_url
      }
      env {
        name  = "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
        value = local.shared_secrets.docintel_endpoint
      }
      env {
        name        = "AZURE_DOCUMENT_INTELLIGENCE_KEY"
        secret_name = "docintel-key"
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.apps_acr_pull,
    azurerm_postgresql_flexible_server_database.researchops,
  ]
}

resource "azurerm_container_app" "indexer" {
  name                         = "${local.combined}-indexer"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  secret {
    name  = "database-url"
    value = local.shared_secrets.db_url
  }
  secret {
    name  = "storage-connection-string"
    value = local.shared_secrets.storage_connection_string
  }
  secret {
    name  = "docintel-key"
    value = local.shared_secrets.docintel_key
  }
  secret {
    name  = "openai-key"
    value = local.shared_secrets.openai_key
  }
  secret {
    name  = "search-admin-key"
    value = local.shared_secrets.search_admin_key
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name    = "indexer"
      image   = var.indexer_image
      cpu     = 0.5
      memory  = "1Gi"
      command = ["python", "-m", "app.search.worker"]

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name  = "STORAGE_DIR"
        value = "/app/storage/uploads"
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER"
        value = azurerm_storage_container.documents.name
      }
      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "storage-connection-string"
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_URL"
        value = local.azure_storage_account_url
      }
      env {
        name  = "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
        value = local.shared_secrets.docintel_endpoint
      }
      env {
        name        = "AZURE_DOCUMENT_INTELLIGENCE_KEY"
        secret_name = "docintel-key"
      }
      env {
        name  = "AZURE_SEARCH_ENDPOINT"
        value = local.shared_secrets.search_endpoint
      }
      env {
        name        = "AZURE_SEARCH_API_KEY"
        secret_name = "search-admin-key"
      }
      env {
        name  = "AZURE_SEARCH_INDEX_NAME"
        value = "researchops-document-chunks"
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = local.shared_secrets.openai_endpoint
      }
      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "openai-key"
      }
      env {
        name  = "AZURE_OPENAI_API_VERSION"
        value = "2024-10-21"
      }
      env {
        name  = "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        value = azurerm_cognitive_deployment.embedding.name
      }
      env {
        name  = "AZURE_OPENAI_EMBEDDING_DIMENSIONS"
        value = "1536"
      }
      env {
        name  = "AZURE_OPENAI_CHAT_DEPLOYMENT"
        value = azurerm_cognitive_deployment.chat.name
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.apps_acr_pull,
    azurerm_postgresql_flexible_server_database.researchops,
    azurerm_cognitive_deployment.chat,
  ]
}

resource "azurerm_container_app" "mcp" {
  name                         = "${local.combined}-mcp"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  ingress {
    external_enabled           = true
    target_port                = 8002
    transport                  = "auto"
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  secret {
    name  = "database-url"
    value = local.shared_secrets.db_url
  }
  secret {
    name  = "storage-connection-string"
    value = local.shared_secrets.storage_connection_string
  }
  secret {
    name  = "mcp-dev-token"
    value = local.shared_secrets.mcp_dev_token
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name    = "mcp"
      image   = var.mcp_image
      cpu     = 0.5
      memory  = "1Gi"
      command = ["uvicorn"]
      args    = ["app.agents.mcp.main:app", "--host", "0.0.0.0", "--port", "8002"]

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name  = "AUTH_MODE"
        value = "development"
      }
      env {
        name  = "DEV_DEFAULT_USER_EMAIL"
        value = "demo.researchops@example.test"
      }
      env {
        name  = "MCP_SERVER_NAME"
        value = "ResearchOps Azure Agent Platform"
      }
      env {
        name        = "MCP_DEV_AGENT_TOKEN"
        secret_name = "mcp-dev-token"
      }
      env {
        name  = "MCP_ALLOWED_ORIGINS"
        value = "${local.frontend_url},${local.backend_url}"
      }
      env {
        name  = "MCP_MAX_RESULTS"
        value = "25"
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER"
        value = azurerm_storage_container.documents.name
      }
      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "storage-connection-string"
      }
      env {
        name  = "STORAGE_DIR"
        value = "/app/storage/uploads"
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.apps_acr_pull,
    azurerm_postgresql_flexible_server_database.researchops,
  ]
}

resource "azurerm_container_app" "frontend" {
  name                         = "${local.combined}-frontend"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  ingress {
    external_enabled           = true
    target_port                = 80
    transport                  = "auto"
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name   = "frontend"
      image  = var.frontend_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "BACKEND_URL"
        value = local.backend_url
      }
      env {
        name  = "MCP_URL"
        value = local.mcp_url
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.apps_acr_pull,
  ]
}
