variable "prefix" {
  description = "Short lowercase prefix for resource naming."
  type        = string
  default     = "researchops"
}

variable "location" {
  description = "Primary Azure region."
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Deployment environment tag."
  type        = string
  default     = "demo"
}

variable "postgres_admin_user" {
  description = "Postgres administrator login."
  type        = string
  default     = "researchops"
}

variable "frontend_image" {
  description = "ACR image reference for the frontend container app."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "backend_image" {
  description = "ACR image reference for the backend FastAPI container app."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "worker_image" {
  description = "ACR image reference for the extraction worker container app."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "indexer_image" {
  description = "ACR image reference for the search indexer container app."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "mcp_image" {
  description = "ACR image reference for the MCP server container app."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "github_repository" {
  description = "GitHub owner/repo allowed to use the OIDC service principal."
  type        = string
  default     = "fullstack-nick/ResearchOps-Platform"
}

variable "openai_embedding_model" {
  description = "Azure OpenAI embedding model name."
  type        = string
  default     = "text-embedding-3-small"
}

variable "openai_embedding_model_version" {
  description = "Azure OpenAI embedding model version."
  type        = string
  default     = "1"
}

variable "openai_chat_model" {
  description = "Azure OpenAI chat completion model name."
  type        = string
  default     = "gpt-4.1-mini"
}

variable "openai_chat_model_version" {
  description = "Azure OpenAI chat completion model version."
  type        = string
  default     = "2025-04-14"
}

variable "postgres_location" {
  description = "Region where the PostgreSQL flexible server is provisioned. Some new subscriptions are blocked from eastus for Postgres."
  type        = string
  default     = "centralus"
}

variable "common_tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default = {
    project = "researchops-azure-agent-platform"
    phase   = "phase-6-deploy"
  }
}

variable "grafana_admin_principal_object_ids" {
  description = "Additional Entra principal object IDs that should receive Grafana Admin on the managed Grafana instance, for example the GitHub Actions OIDC service principal."
  type        = list(string)
  default     = ["2b378932-f32b-4577-84ab-73d8fc5ae314"]
}
