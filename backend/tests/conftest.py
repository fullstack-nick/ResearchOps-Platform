from __future__ import annotations

import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

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
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "8")

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

    from app.search import service as search_service

    search_store: dict[str, dict[str, Any]] = {}

    def fake_search_download_blob(
        settings: object, container: str, object_key: str
    ) -> bytes:
        return blob_store[object_key]

    def fake_analyze_document_text(
        settings: object, document_bytes: bytes
    ) -> dict[str, Any]:
        return {
            "pages": [
                {
                    "page_number": 1,
                    "lines": [
                        {"content": "Helix Lab Supplies GmbH invoice HLS-2026-0142."},
                        {
                            "content": "Invoice total is 4010.30 EUR and the due "
                            "date is 2026-05-15."
                        },
                        {
                            "content": "Project code BIO-OPS-2026-014 covers "
                            "single-cell reagent kits."
                        },
                    ],
                },
                {
                    "page_number": 2,
                    "lines": [
                        {"content": "Delivery is scheduled for the Helix campus dock."},
                        {"content": "Payment terms are net 14 days from issue date."},
                    ],
                },
            ]
        }

    def fake_ensure_search_index(settings: object) -> None:
        return None

    def fake_embed_texts(settings: object, texts: list[str]) -> list[list[float]]:
        dimensions = get_settings().azure_openai_embedding_dimensions
        return [
            [
                float((sum(ord(char) for char in text) + index) % 5)
                for index in range(dimensions)
            ]
            for text in texts
        ]

    def fake_upload_chunk_documents(
        settings: object, documents: list[dict[str, Any]]
    ) -> None:
        for document in documents:
            search_store[str(document["chunk_id"])] = dict(document)

    def fake_delete_chunks_from_index(settings: object, document_id: str) -> None:
        stale = [
            key
            for key, value in search_store.items()
            if value["document_id"] == document_id
        ]
        for key in stale:
            del search_store[key]

    def fake_search_document_chunks(
        settings: object,
        document_id: str,
        query: str,
        vector: list[float],
        top: int,
    ) -> list[dict[str, Any]]:
        matches = sorted(
            (
                value
                for value in search_store.values()
                if value["document_id"] == document_id
            ),
            key=lambda value: value["chunk_index"],
        )
        results: list[dict[str, Any]] = []
        for rank, document in enumerate(matches[:top]):
            results.append(
                {
                    "chunk_id": document["chunk_id"],
                    "document_id": document["document_id"],
                    "chunk_index": document["chunk_index"],
                    "page_number": document.get("page_number"),
                    "content": document["content"],
                    "score": round(1.0 - rank * 0.1, 4),
                }
            )
        return results

    def fake_generate_grounded_answer(
        settings: object, question: str, chunks: list[dict[str, Any]]
    ) -> str:
        snippet = chunks[0]["content"][:160] if chunks else ""
        return f"Based on [Source 1]: {snippet}"

    monkeypatch.setattr(search_service, "download_document_blob", fake_search_download_blob)
    monkeypatch.setattr(search_service, "analyze_document_text", fake_analyze_document_text)
    monkeypatch.setattr(search_service, "ensure_search_index", fake_ensure_search_index)
    monkeypatch.setattr(search_service, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(
        search_service, "upload_chunk_documents", fake_upload_chunk_documents
    )
    monkeypatch.setattr(
        search_service, "delete_chunks_from_index", fake_delete_chunks_from_index
    )
    monkeypatch.setattr(
        search_service, "search_document_chunks", fake_search_document_chunks
    )
    monkeypatch.setattr(
        search_service, "generate_grounded_answer", fake_generate_grounded_answer
    )
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
