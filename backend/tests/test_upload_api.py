from __future__ import annotations

from httpx import AsyncClient


async def test_upload_creates_document_workflow_and_audit_events(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    response = await client.post(
        "/api/documents?workflow_type=procurement",
        files={"file": ("../invoice.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    document = body["document"]
    document_id = document["id"]
    assert document["original_filename"] == "../invoice.pdf"
    assert document["safe_filename"] == "invoice.pdf"
    assert document["workflow_type"] == "procurement"
    assert document["status"] == "extraction_pending"
    assert document["extraction_summary"]["status"] == "pending"
    assert document["workflow"]["status"] == "awaiting_review"
    assert document["workflow"]["steps"][0]["assigned_role"] == "operations_admin"
    assert document["versions"][0]["version_number"] == 1
    assert document["versions"][0]["storage_provider"] == "azure_blob"
    assert document["versions"][0]["storage_container"] == "test-documents"

    documents = await client.get("/api/documents?workflow_type=procurement")
    assert documents.status_code == 200
    assert documents.json()["documents"][0]["id"] == document_id

    detail = await client.get(f"/api/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == document_id

    file_response = await client.get(f"/api/documents/{document_id}/file")
    assert file_response.status_code == 200
    assert file_response.content.startswith(b"%PDF")
    assert file_response.headers["content-disposition"].startswith("inline;")

    audit = await client.get(f"/api/audit-events?document_id={document_id}")
    assert audit.status_code == 200
    event_types = {event["event_type"] for event in audit.json()["audit_events"]}
    assert {"document.uploaded", "workflow.created", "extraction.requested"} <= event_types


async def test_dashboard_summary_counts_uploaded_documents(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    await client.post(
        "/api/documents?workflow_type=hr_onboarding",
        files={"file": ("onboarding.pdf", pdf_bytes, "application/pdf")},
    )

    response = await client.get("/api/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_documents"] == 1
    assert body["awaiting_review"] == 1
    assert body["recent_failures"] == 0
    assert body["documents_with_missing_fields"] == 0
    assert body["documents_by_workflow"] == [{"workflow_type": "hr_onboarding", "count": 1}]


async def test_openapi_and_health_endpoints(client: AsyncClient) -> None:
    health = await client.get("/healthz")
    ready = await client.get("/readyz")
    openapi = await client.get("/openapi.json")

    assert health.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}
    assert openapi.status_code == 200
    assert "/api/documents" in openapi.json()["paths"]


async def test_rejects_non_pdf_uploads(client: AsyncClient) -> None:
    response = await client.post(
        "/api/documents?workflow_type=procurement",
        files={"file": ("invoice.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 415


async def test_rejects_invalid_workflow_type(client: AsyncClient, pdf_bytes: bytes) -> None:
    response = await client.post(
        "/api/documents?workflow_type=unknown",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 422
