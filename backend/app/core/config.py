from functools import lru_cache
from pathlib import Path

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ResearchOps API"
    environment: str = "local"
    database_url: str = Field(
        default="postgresql+asyncpg://researchops:researchops@localhost:5432/researchops"
    )
    frontend_origin: str = "http://localhost:5173"
    storage_dir: Path = Path("storage/uploads")
    max_upload_bytes: int = 20 * 1024 * 1024
    azure_storage_container: str | None = None
    azure_storage_connection_string: str | None = None
    azure_storage_account_url: AnyUrl | str | None = None
    azure_document_intelligence_endpoint: AnyUrl | str | None = None
    azure_document_intelligence_key: str | None = None
    azure_document_intelligence_model_id: str = "prebuilt-invoice"
    azure_document_intelligence_read_model_id: str = "prebuilt-read"
    extraction_worker_poll_seconds: float = 2.0
    extraction_worker_batch_size: int = 5
    azure_search_endpoint: AnyUrl | str | None = None
    azure_search_api_key: str | None = None
    azure_search_index_name: str = "researchops-document-chunks"
    azure_openai_endpoint: AnyUrl | str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_embedding_dimensions: int = 1536
    azure_openai_chat_deployment: str = "gpt-4o-mini"
    indexing_worker_poll_seconds: float = 2.0
    indexing_chunk_size: int = 1200
    indexing_chunk_overlap: int = 200
    qa_top_chunks: int = 5
    auth_mode: str = "development"
    entra_tenant_id: str | None = None
    entra_client_id: str | None = None
    entra_audience: str | None = None
    entra_required_scope: str = "access_as_user"
    dev_default_user_email: str = "demo.researchops@example.test"
    dev_default_user_roles: str = "operations_admin,researcher"
    dev_default_research_group: str = "operations"
    applicationinsights_connection_string: str | None = None
    observability_enabled: bool = False
    observability_sample_rate: float = 1.0
    otel_service_name: str | None = None
    otel_resource_attributes: str = ""
    mcp_server_name: str = "ResearchOps Azure Agent Platform"
    mcp_dev_agent_token: str = "local-dev-agent-token"  # noqa: S105
    mcp_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    mcp_allowed_agent_client_ids: str = ""
    mcp_max_results: int = 25
    mcp_service_user_email: str = "agent.researchops@example.test"

    @property
    def has_azure_storage_config(self) -> bool:
        return bool(
            self.azure_storage_container
            and (self.azure_storage_connection_string or self.azure_storage_account_url)
        )

    @property
    def frontend_origin_values(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.frontend_origin.split(",")
            if origin.strip()
        ]

    @property
    def has_document_intelligence_config(self) -> bool:
        return bool(self.azure_document_intelligence_endpoint)

    @property
    def has_azure_search_config(self) -> bool:
        return bool(self.azure_search_endpoint)

    @property
    def has_azure_openai_config(self) -> bool:
        return bool(self.azure_openai_endpoint)

    @property
    def entra_authority(self) -> str | None:
        return (
            f"https://login.microsoftonline.com/{self.entra_tenant_id}"
            if self.entra_tenant_id
            else None
        )

    @property
    def entra_jwks_uri(self) -> str | None:
        return (
            f"{self.entra_authority}/discovery/v2.0/keys" if self.entra_authority else None
        )

    @property
    def entra_issuer(self) -> str | None:
        return f"{self.entra_authority}/v2.0" if self.entra_authority else None

    @property
    def is_entra_auth(self) -> bool:
        return self.auth_mode.lower() == "entra"

    @property
    def mcp_allowed_origin_values(self) -> set[str]:
        return {
            origin.strip()
            for origin in self.mcp_allowed_origins.split(",")
            if origin.strip()
        }

    @property
    def mcp_allowed_agent_client_id_values(self) -> set[str]:
        return {
            client_id.strip()
            for client_id in self.mcp_allowed_agent_client_ids.split(",")
            if client_id.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
