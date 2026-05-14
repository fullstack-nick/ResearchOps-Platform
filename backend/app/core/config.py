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


@lru_cache
def get_settings() -> Settings:
    return Settings()
