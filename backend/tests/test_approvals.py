from __future__ import annotations

from typing import Any

from httpx import AsyncClient


async def upload_as(
    client: AsyncClient,
    pdf_bytes: bytes,
    workflow_type: str,
    email: str,
    filename: str = "doc.pdf",
) -> dict[str, Any]:
    response = await client.post(
        f"/api/documents?workflow_type={workflow_type}",
        files={"file": (filename, pdf_bytes, "application/pdf")},
        headers={"X-Dev-User-Email": email},
    )
    assert response.status_code == 201, response.text
    document: dict[str, Any] = response.json()["document"]
    return document


async def test_upload_creates_full_approval_chain(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document = await upload_as(
        client, pdf_bytes, "procurement", "researcher.alice@example.test"
    )

    steps = document["workflow"]["steps"]
    assert [step["step_name"] for step in steps] == [
        "intake_review",
        "group_lead_approval",
        "finance_approval",
    ]
    assert [step["assigned_role"] for step in steps] == [
        "operations_admin",
        "group_lead",
        "finance",
    ]
    assert [step["step_order"] for step in steps] == [0, 1, 2]
    assert all(step["status"] == "pending" for step in steps)
    assert document["workflow"]["current_step"] == "intake_review"


async def test_approval_chain_advances_then_completes(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document = await upload_as(
        client, pdf_bytes, "procurement", "researcher.alice@example.test"
    )
    workflow_id = document["workflow"]["id"]
    steps = document["workflow"]["steps"]
    step_by_name = {step["step_name"]: step["id"] for step in steps}

    intake_decision = await client.post(
        f"/api/workflows/{workflow_id}/steps/{step_by_name['intake_review']}/decision",
        json={"decision": "approved", "reason": "intake complete"},
        headers={"X-Dev-User-Email": "admin.frank@example.test"},
    )
    assert intake_decision.status_code == 200, intake_decision.text
    assert intake_decision.json()["current_step"] == "group_lead_approval"

    group_decision = await client.post(
        f"/api/workflows/{workflow_id}/steps/{step_by_name['group_lead_approval']}/decision",
        json={"decision": "approved"},
        headers={"X-Dev-User-Email": "lead.bob@example.test"},
    )
    assert group_decision.status_code == 200, group_decision.text
    assert group_decision.json()["current_step"] == "finance_approval"

    finance_decision = await client.post(
        f"/api/workflows/{workflow_id}/steps/{step_by_name['finance_approval']}/decision",
        json={"decision": "approved"},
        headers={"X-Dev-User-Email": "finance.carol@example.test"},
    )
    assert finance_decision.status_code == 200, finance_decision.text
    body = finance_decision.json()
    assert body["status"] == "approved"
    assert body["current_step"] == "completed"

    audit = await client.get(
        f"/api/audit-events?document_id={document['id']}",
        headers={"X-Dev-User-Email": "admin.frank@example.test"},
    )
    event_types = {event["event_type"] for event in audit.json()["audit_events"]}
    assert {"approval.granted", "workflow.advanced", "workflow.completed"} <= event_types


async def test_rejection_short_circuits_chain(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document = await upload_as(
        client, pdf_bytes, "procurement", "researcher.alice@example.test"
    )
    workflow_id = document["workflow"]["id"]
    intake_id = document["workflow"]["steps"][0]["id"]

    rejection = await client.post(
        f"/api/workflows/{workflow_id}/steps/{intake_id}/decision",
        json={"decision": "rejected", "reason": "supplier on hold list"},
        headers={"X-Dev-User-Email": "admin.frank@example.test"},
    )
    assert rejection.status_code == 200, rejection.text
    body = rejection.json()
    assert body["status"] == "rejected"
    remaining_statuses = {step["status"] for step in body["steps"][1:]}
    assert remaining_statuses == {"skipped"}


async def test_role_required_to_decide_step(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document = await upload_as(
        client, pdf_bytes, "procurement", "researcher.alice@example.test"
    )
    workflow_id = document["workflow"]["id"]
    intake_id = document["workflow"]["steps"][0]["id"]

    response = await client.post(
        f"/api/workflows/{workflow_id}/steps/{intake_id}/decision",
        json={"decision": "approved"},
        headers={"X-Dev-User-Email": "researcher.alice@example.test"},
    )

    assert response.status_code == 403


async def test_group_lead_locked_to_own_research_group(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document = await upload_as(
        client, pdf_bytes, "grants", "admin.frank@example.test"
    )
    workflow_id = document["workflow"]["id"]
    steps = {step["step_name"]: step["id"] for step in document["workflow"]["steps"]}

    intake = await client.post(
        f"/api/workflows/{workflow_id}/steps/{steps['intake_review']}/decision",
        json={"decision": "approved"},
        headers={"X-Dev-User-Email": "admin.frank@example.test"},
    )
    assert intake.status_code == 200, intake.text

    # admin.frank uploaded, so document.research_group == 'operations'. Bob is in
    # 'genomics' so he must not be able to approve this document.
    forbidden = await client.post(
        f"/api/workflows/{workflow_id}/steps/{steps['group_lead_approval']}/decision",
        json={"decision": "approved"},
        headers={"X-Dev-User-Email": "lead.bob@example.test"},
    )
    assert forbidden.status_code == 403


async def test_decision_out_of_order_returns_409(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document = await upload_as(
        client, pdf_bytes, "procurement", "researcher.alice@example.test"
    )
    workflow_id = document["workflow"]["id"]
    steps = {step["step_name"]: step["id"] for step in document["workflow"]["steps"]}

    response = await client.post(
        f"/api/workflows/{workflow_id}/steps/{steps['finance_approval']}/decision",
        json={"decision": "approved"},
        headers={"X-Dev-User-Email": "finance.carol@example.test"},
    )

    assert response.status_code == 409


async def test_workflow_state_endpoint_indicates_decidability(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    document = await upload_as(
        client, pdf_bytes, "hr_onboarding", "admin.frank@example.test"
    )
    workflow_id = document["workflow"]["id"]

    bob_view = await client.get(
        f"/api/workflows/{workflow_id}",
        headers={"X-Dev-User-Email": "lead.bob@example.test"},
    )
    # Bob is a group lead and doesn't have access to HR onboarding documents.
    assert bob_view.status_code == 404

    dan_view = await client.get(
        f"/api/workflows/{workflow_id}",
        headers={"X-Dev-User-Email": "hr.dan@example.test"},
    )
    assert dan_view.status_code == 200
    state = dan_view.json()
    assert state["current_step"] == "intake_review"
    # HR can't decide the intake_review step (operations_admin role required).
    assert state["can_decide_current_step"] is False
