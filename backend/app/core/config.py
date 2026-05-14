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
    frontend_origin: AnyUrl | str = "http://localhost:5173"
    storage_dir: Path = Path("storage/uploads")
    max_upload_bytes: int = 20 * 1024 * 1024
    azure_storage_container: str | None = None
    azure_storage_connection_string: str | None = None
    azure_storage_account_url: AnyUrl | str | None = None
    azure_document_intelligence_endpoint: AnyUrl | str | None = None
    azure_document_intelligence_key: str | None = None
    azure_document_intelligence_model_id: str = "prebuilt-invoice"
    extraction_worker_poll_seconds: float = 2.0
    extraction_worker_batch_size: int = 5

    @property
    def has_azure_storage_config(self) -> bool:
        return bool(
            self.azure_storage_container
            and (self.azure_storage_connection_string or self.azure_storage_account_url)
        )

    @property
    def has_document_intelligence_config(self) -> bool:
        return bool(self.azure_document_intelligence_endpoint)


@lru_cache
def get_settings() -> Settings:
    return Settings()
