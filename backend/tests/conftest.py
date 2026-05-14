from __future__ import annotations

import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str]:
    with PostgresContainer("postgres:18.3") as postgres:
        raw_url = postgres.get_connection_url()
        yield raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")


@pytest.fixture()
def configured_app(
    postgres_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> FastAPI:
    monkeypatch.setenv("DATABASE_URL", postgres_url)
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")

    from app.core.config import get_settings

    get_settings.cache_clear()
    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")

    from app.main import create_app

    app = create_app()
    blob_store: dict[str, bytes] = {}

    from app.documents import service as document_service
    from app.documents.azure_storage import BlobUploadResult

    def fake_upload_document_blob(
        settings: object,
        object_key: str,
        content: bytes,
        content_type: str,
        metadata: dict[str, str],
    ) -> BlobUploadResult:
        blob_store[object_key] = content
        return BlobUploadResult(
            container="test-documents",
            object_key=object_key,
            url=f"https://storage.example.test/test-documents/{object_key}",
            etag="test-etag",
        )

    def fake_download_document_blob(
        settings: object,
        container: str,
        object_key: str,
    ) -> bytes:
        return blob_store[object_key]

    monkeypatch.setattr(document_service, "upload_document_blob", fake_upload_document_blob)
    monkeypatch.setattr(document_service, "download_document_blob", fake_download_document_blob)
    return app


@pytest.fixture()
async def client(configured_app: FastAPI) -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=configured_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    from app.database.session import engine

    await engine.dispose()


@pytest.fixture()
def pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 0>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF"
    )
