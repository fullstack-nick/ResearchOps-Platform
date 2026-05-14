from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


async def upload_document(
    client: AsyncClient, pdf_bytes: bytes, workflow_type: str = "contracts"
) -> str:
    response = await client.post(
        f"/api/documents?workflow_type={workflow_type}",
        files={"file": ("document.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["document"]["id"])


async def process_pending_indexing_run() -> bool:
    from app.database.session import AsyncSessionLocal
    from app.search.service import process_next_pending_indexing_run

    async with AsyncSessionLocal() as session:
        return await process_next_pending_indexing_run(session)


async def test_upload_creates_pending_indexing_run(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document_id = await upload_document(client, pdf_bytes, "contracts")

    response = await client.get(f"/api/documents/{document_id}/indexing")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["latest_run"]["status"] == "pending"
    assert body["chunk_count"] == 0
    assert body["chunks"] == []

    audit = await client.get(f"/api/audit-events?document_id={document_id}")
    event_types = {event["event_type"] for event in audit.json()["audit_events"]}
    assert "indexing.requested" in event_types


async def test_indexer_persists_chunks_for_any_workflow_type(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document_id = await upload_document(client, pdf_bytes, "hr_onboarding")

    assert await process_pending_indexing_run() is True

    response = await client.get(f"/api/documents/{document_id}/indexing")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["chunk_count"] >= 2
    assert body["latest_run"]["chunk_count"] == body["chunk_count"]
    assert len(body["chunks"]) == body["chunk_count"]
    assert body["chunks"][0]["page_number"] == 1
    assert "Helix Lab Supplies" in body["chunks"][0]["content"]

    audit = await client.get(f"/api/audit-events?document_id={document_id}")
    event_types = {event["event_type"] for event in audit.json()["audit_events"]}
    assert {"indexing.started", "indexing.completed"} <= event_types


async def test_question_returns_grounded_answer_with_citations(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document_id = await upload_document(client, pdf_bytes, "procurement")
    assert await process_pending_indexing_run() is True

    response = await client.post(
        f"/api/documents/{document_id}/questions",
        json={"question": "What is the invoice total?"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["answer"] is not None
    assert "4010.30" in body["answer"]
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["page_number"] == 1
    assert body["citations"][0]["chunk_id"]

    history = await client.get(f"/api/documents/{document_id}/questions")
    assert history.status_code == 200
    questions = history.json()["questions"]
    assert len(questions) == 1
    assert questions[0]["question"] == "What is the invoice total?"
    assert questions[0]["status"] == "completed"

    audit = await client.get(f"/api/audit-events?document_id={document_id}")
    event_types = {event["event_type"] for event in audit.json()["audit_events"]}
    assert "document.question_asked" in event_types


async def test_question_before_indexing_completes_returns_409(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document_id = await upload_document(client, pdf_bytes, "grants")

    response = await client.post(
        f"/api/documents/{document_id}/questions",
        json={"question": "When is the next report due?"},
    )

    assert response.status_code == 409


async def test_question_records_failure_when_generation_errors(
    client: AsyncClient, pdf_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.search import service as search_service

    document_id = await upload_document(client, pdf_bytes, "reports")
    assert await process_pending_indexing_run() is True

    def failing_generate(
        settings: object, question: str, chunks: list[dict[str, Any]]
    ) -> str:
        raise RuntimeError("chat completion unavailable")

    monkeypatch.setattr(search_service, "generate_grounded_answer", failing_generate)

    response = await client.post(
        f"/api/documents/{document_id}/questions",
        json={"question": "What decisions were made?"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert body["answer"] is None
    assert body["error_message"]

    audit = await client.get(f"/api/audit-events?document_id={document_id}")
    event_types = {event["event_type"] for event in audit.json()["audit_events"]}
    assert "document.question_failed" in event_types


async def test_indexer_failure_and_retry(
    client: AsyncClient, pdf_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.search import service as search_service

    document_id = await upload_document(client, pdf_bytes, "contracts")

    def failing_analyze(settings: object, document_bytes: bytes) -> dict[str, Any]:
        raise RuntimeError("read model unavailable")

    monkeypatch.setattr(search_service, "analyze_document_text", failing_analyze)
    assert await process_pending_indexing_run() is True

    failed = await client.get(f"/api/documents/{document_id}/indexing")
    assert failed.json()["status"] == "failed"
    assert failed.json()["latest_run"]["error_message"]

    retry = await client.post(f"/api/documents/{document_id}/indexing/retry")
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "pending"
