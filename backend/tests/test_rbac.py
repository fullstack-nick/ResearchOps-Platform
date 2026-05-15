from __future__ import annotations

from httpx import AsyncClient


async def upload_as(
    client: AsyncClient,
    pdf_bytes: bytes,
    workflow_type: str,
    email: str,
    filename: str = "doc.pdf",
) -> str:
    response = await client.post(
        f"/api/documents?workflow_type={workflow_type}",
        files={"file": (filename, pdf_bytes, "application/pdf")},
        headers={"X-Dev-User-Email": email},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["document"]["id"])


async def test_researcher_only_sees_own_documents(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    alice = "researcher.alice@example.test"
    admin = "admin.frank@example.test"
    alice_doc_id = await upload_as(client, pdf_bytes, "grants", alice, "alice.pdf")
    await upload_as(client, pdf_bytes, "grants", admin, "admin.pdf")

    listing = await client.get(
        "/api/documents", headers={"X-Dev-User-Email": alice}
    )

    assert listing.status_code == 200
    visible_ids = {doc["id"] for doc in listing.json()["documents"]}
    assert visible_ids == {alice_doc_id}


async def test_finance_sees_procurement_only(client: AsyncClient, pdf_bytes: bytes) -> None:
    finance = "finance.carol@example.test"
    procurement_id = await upload_as(client, pdf_bytes, "procurement", finance, "po.pdf")
    other_id = await upload_as(client, pdf_bytes, "hr_onboarding", finance, "hr.pdf")

    listing = await client.get(
        "/api/documents", headers={"X-Dev-User-Email": finance}
    )

    visible_ids = {doc["id"] for doc in listing.json()["documents"]}
    assert procurement_id in visible_ids
    # HR doc shows because finance also owns it (uploader is owner).
    assert other_id in visible_ids

    # Same finance user filtering for hr_onboarding from a colleague is forbidden.
    admin_hr = await upload_as(
        client, pdf_bytes, "hr_onboarding", "admin.frank@example.test", "admin-hr.pdf"
    )
    forbidden = await client.get(
        f"/api/documents/{admin_hr}",
        headers={"X-Dev-User-Email": finance},
    )
    assert forbidden.status_code == 404


async def test_hr_user_can_view_hr_documents(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    admin = "admin.frank@example.test"
    hr_doc_id = await upload_as(client, pdf_bytes, "hr_onboarding", admin, "onb.pdf")

    response = await client.get(
        f"/api/documents/{hr_doc_id}",
        headers={"X-Dev-User-Email": "hr.dan@example.test"},
    )

    assert response.status_code == 200


async def test_dashboard_summary_filtered_for_researcher(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    alice = "researcher.alice@example.test"
    admin = "admin.frank@example.test"
    await upload_as(client, pdf_bytes, "grants", alice, "alice1.pdf")
    await upload_as(client, pdf_bytes, "grants", alice, "alice2.pdf")
    await upload_as(client, pdf_bytes, "grants", admin, "admin1.pdf")

    response = await client.get(
        "/api/dashboard/summary", headers={"X-Dev-User-Email": alice}
    )

    body = response.json()
    assert body["total_documents"] == 2
    assert body["documents_by_workflow"] == [{"workflow_type": "grants", "count": 2}]
