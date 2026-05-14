from __future__ import annotations

from typing import Any

from httpx import AsyncClient


def fake_invoice_result() -> dict[str, Any]:
    return {
        "model_id": "prebuilt-invoice",
        "documents": [
            {
                "fields": {
                    "VendorName": {
                        "valueString": "Helix Lab Supplies GmbH",
                        "content": "Helix Lab Supplies GmbH",
                        "confidence": 0.99,
                        "boundingRegions": [{"pageNumber": 1, "polygon": [1, 1, 3, 1, 3, 2, 1, 2]}],
                    },
                    "InvoiceId": {"valueString": "HLS-2026-0142", "confidence": 0.97},
                    "InvoiceDate": {"valueDate": "2026-05-01", "confidence": 0.96},
                    "DueDate": {"valueDate": "2026-05-15", "confidence": 0.95},
                    "SubTotal": {
                        "valueCurrency": {"amount": 3370.0, "currencyCode": "EUR"},
                        "confidence": 0.94,
                    },
                    "TotalTax": {
                        "valueCurrency": {"amount": 640.3, "currencyCode": "EUR"},
                        "confidence": 0.93,
                    },
                    "InvoiceTotal": {
                        "valueCurrency": {"amount": 4010.3, "currencyCode": "EUR"},
                        "confidence": 0.98,
                    },
                    "Items": {
                        "valueArray": [
                            {
                                "confidence": 0.92,
                                "valueObject": {
                                    "Description": {
                                        "valueString": "Single-cell reagent kit",
                                        "confidence": 0.91,
                                    },
                                    "Quantity": {"valueNumber": 2, "confidence": 0.9},
                                    "UnitPrice": {
                                        "valueCurrency": {
                                            "amount": 1200.0,
                                            "currencyCode": "EUR",
                                        },
                                        "confidence": 0.9,
                                    },
                                    "Amount": {
                                        "valueCurrency": {
                                            "amount": 2400.0,
                                            "currencyCode": "EUR",
                                        },
                                        "confidence": 0.9,
                                    },
                                },
                            }
                        ]
                    },
                }
            }
        ],
    }


async def upload_procurement_document(client: AsyncClient, pdf_bytes: bytes) -> str:
    response = await client.post(
        "/api/documents?workflow_type=procurement",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["document"]["id"])


async def process_pending_run(pdf_bytes: bytes) -> bool:
    from app.database.session import AsyncSessionLocal
    from app.extraction.service import process_next_pending_run

    def analyze(settings: object, document_bytes: bytes) -> dict[str, Any]:
        assert document_bytes == pdf_bytes
        return fake_invoice_result()

    def download(settings: object, container: str, object_key: str) -> bytes:
        return pdf_bytes

    async with AsyncSessionLocal() as session:
        return await process_next_pending_run(session, analyze=analyze, download_blob=download)


async def test_procurement_upload_creates_pending_extraction_run(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document_id = await upload_procurement_document(client, pdf_bytes)

    response = await client.get(f"/api/documents/{document_id}/extraction")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["status"] == "pending"
    assert body["latest_run"]["status"] == "pending"
    assert body["fields"] == []


async def test_worker_persists_invoice_fields_line_items_and_missing_fields(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document_id = await upload_procurement_document(client, pdf_bytes)

    assert await process_pending_run(pdf_bytes) is True

    response = await client.get(f"/api/documents/{document_id}/extraction")
    assert response.status_code == 200
    body = response.json()
    fields = {field["field_key"]: field for field in body["fields"]}
    assert body["status"] == "completed"
    assert fields["vendor_name"]["display_value"] == "Helix Lab Supplies GmbH"
    assert fields["gross_total"]["display_value"] == "4010.30"
    assert fields["currency"]["display_value"] == "EUR"
    assert fields["vendor_name"]["confidence"] == 0.99
    assert body["line_items"][0]["description"] == "Single-cell reagent kit"
    assert body["missing_fields"] == ["purchase_order_number"]

    detail = await client.get(f"/api/documents/{document_id}")
    assert detail.json()["status"] == "extracted"
    assert detail.json()["extraction_summary"]["missing_field_count"] == 1


async def test_field_correction_updates_missing_fields_and_audit(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document_id = await upload_procurement_document(client, pdf_bytes)
    assert await process_pending_run(pdf_bytes) is True

    extraction = await client.get(f"/api/documents/{document_id}/extraction")
    purchase_order = next(
        field
        for field in extraction.json()["fields"]
        if field["field_key"] == "purchase_order_number"
    )

    correction = await client.patch(
        f"/api/documents/{document_id}/fields/{purchase_order['id']}",
        json={"corrected_value": "PO-2026-001", "reason": "Found in requester email."},
    )

    assert correction.status_code == 200, correction.text
    assert correction.json()["display_value"] == "PO-2026-001"
    after = await client.get(f"/api/documents/{document_id}/extraction")
    assert after.json()["missing_fields"] == []
    audit = await client.get(f"/api/audit-events?document_id={document_id}")
    event_types = {event["event_type"] for event in audit.json()["audit_events"]}
    assert "field.corrected" in event_types


async def test_worker_failure_and_retry(client: AsyncClient, pdf_bytes: bytes) -> None:
    document_id = await upload_procurement_document(client, pdf_bytes)

    from app.database.session import AsyncSessionLocal
    from app.extraction.service import process_next_pending_run

    def analyze(settings: object, document_bytes: bytes) -> dict[str, Any]:
        raise RuntimeError("service unavailable")

    def download(settings: object, container: str, object_key: str) -> bytes:
        return pdf_bytes

    async with AsyncSessionLocal() as session:
        assert await process_next_pending_run(session, analyze=analyze, download_blob=download)

    failed = await client.get(f"/api/documents/{document_id}/extraction")
    assert failed.json()["status"] == "failed"
    detail = await client.get(f"/api/documents/{document_id}")
    assert detail.json()["status"] == "extraction_failed"

    retry = await client.post(f"/api/documents/{document_id}/extraction/retry")
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "pending"
