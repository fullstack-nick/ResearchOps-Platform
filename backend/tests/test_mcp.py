from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select


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
    return response.json()["document"]  # type: ignore[no-any-return]


@asynccontextmanager
async def mcp_context(email: str) -> AsyncGenerator[None]:
    from app.agents.mcp.auth import (
        McpAuthContext,
        reset_mcp_auth_context,
        set_mcp_auth_context_for_test,
    )
    from app.auth.service import get_user_by_email
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        agent = await get_user_by_email(session, "agent.researchops@example.test")
        user = await get_user_by_email(session, email)
        assert agent is not None
        assert user is not None
    token = set_mcp_auth_context_for_test(
        McpAuthContext(
            agent_user=agent,
            delegated_user=user,
            agent_name="agent.researchops@example.test",
            correlation_id="test-correlation-id",
            source_ip="127.0.0.1",
        )
    )
    try:
        yield
    finally:
        reset_mcp_auth_context(token)


async def seed_invoice_extraction(document_id: str) -> None:
    from app.database.models import ExtractedField, ExtractedLineItem, ExtractionRun
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        run = (
            await session.execute(
                select(ExtractionRun)
                .where(ExtractionRun.document_id == document_id)
                .order_by(ExtractionRun.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
        run.status = "completed"
        run.missing_fields = ["purchase_order_number"]
        session.add_all(
            [
                ExtractedField(
                    document_id=run.document_id,
                    extraction_run_id=run.id,
                    field_key="vendor_name",
                    label="Vendor name",
                    value="Helix Lab Supplies GmbH",
                    value_type="string",
                    confidence=0.98,
                    source_page=1,
                    source_regions=[],
                    raw_value={},
                    is_missing=False,
                    display_order=1,
                ),
                ExtractedField(
                    document_id=run.document_id,
                    extraction_run_id=run.id,
                    field_key="gross_total",
                    label="Gross total",
                    value="4010.30",
                    value_type="currency",
                    confidence=0.94,
                    source_page=1,
                    source_regions=[],
                    raw_value={},
                    is_missing=False,
                    display_order=2,
                ),
                ExtractedField(
                    document_id=run.document_id,
                    extraction_run_id=run.id,
                    field_key="purchase_order_number",
                    label="Purchase order number",
                    value=None,
                    value_type="string",
                    confidence=None,
                    source_page=None,
                    source_regions=[],
                    raw_value=None,
                    is_missing=True,
                    display_order=3,
                ),
                ExtractedLineItem(
                    document_id=run.document_id,
                    extraction_run_id=run.id,
                    item_index=0,
                    description="Single-cell reagent kit",
                    quantity=2,
                    unit_price=1600.0,
                    amount=3200.0,
                    currency="EUR",
                    confidence=0.9,
                    source_page=1,
                    source_regions=[],
                    raw_value={},
                ),
            ]
        )
        await session.commit()


async def agent_action_count() -> int:
    from app.database.models import AgentAction
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        return (
            await session.execute(select(func.count()).select_from(AgentAction))
        ).scalar_one()


async def test_mcp_tool_discovery_over_streamable_http(
    configured_app: FastAPI,
) -> None:
    from app.agents.mcp.main import create_app
    from app.database.session import engine

    app = create_app()
    transport = ASGITransport(app=app)
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
        "X-MCP-Agent-Token": "local-dev-agent-token",
        "X-Dev-User-Email": "admin.frank@example.test",
    }
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://mcp.test") as client:
            response = await client.post(
                "/mcp",
                headers=headers,
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )

    assert configured_app is not None
    assert response.status_code == 200, response.text
    tool_names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert {
        "search_documents",
        "get_document_summary",
        "approve_request",
        "export_audit_log",
    } <= tool_names
    await engine.dispose()


async def test_mcp_origin_validation_denies_untrusted_origin(
    configured_app: FastAPI,
) -> None:
    from app.agents.mcp.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://mcp.test") as client:
        response = await client.post(
            "/mcp",
            headers={
                "Origin": "https://evil.example.test",
                "X-MCP-Agent-Token": "local-dev-agent-token",
                "X-Dev-User-Email": "admin.frank@example.test",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )

    assert configured_app is not None
    assert response.status_code == 403


async def test_search_documents_respects_rbac_and_logs_agent_action(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    from app.agents.mcp import service as mcp_service

    procurement = await upload_as(
        client,
        pdf_bytes,
        "procurement",
        "researcher.alice@example.test",
        "invoice.pdf",
    )
    await upload_as(
        client,
        pdf_bytes,
        "hr_onboarding",
        "admin.frank@example.test",
        "onboarding.pdf",
    )

    async with mcp_context("finance.carol@example.test"):
        result = await mcp_service.search_documents("invoice")

    assert result["count"] == 1
    assert result["documents"][0]["document_id"] == procurement["id"]
    assert await agent_action_count() == 1


async def test_document_fields_and_missing_fields_tools(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    from app.agents.mcp import service as mcp_service

    document = await upload_as(
        client,
        pdf_bytes,
        "procurement",
        "researcher.alice@example.test",
        "invoice.pdf",
    )
    await seed_invoice_extraction(document["id"])

    async with mcp_context("finance.carol@example.test"):
        fields = await mcp_service.get_document_fields(UUID(document["id"]))
        missing = await mcp_service.list_missing_fields(UUID(document["id"]))

    assert fields["available"] is True
    assert fields["fields"][0]["field_key"] == "vendor_name"
    assert fields["line_items"][0]["description"] == "Single-cell reagent kit"
    assert missing["missing_fields"] == ["purchase_order_number"]
    assert await agent_action_count() == 2


async def test_create_approval_request_writes_audit_and_action(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    from app.agents.mcp import service as mcp_service
    from app.database.models import AuditEvent
    from app.database.session import AsyncSessionLocal

    document = await upload_as(
        client,
        pdf_bytes,
        "procurement",
        "researcher.alice@example.test",
        "invoice.pdf",
    )

    async with mcp_context("admin.frank@example.test"):
        result = await mcp_service.create_approval_request(
            UUID(document["workflow"]["id"]),
            reason="Missing PO number needs intake review.",
        )

    assert result["pending_step"] == "intake_review"
    async with AsyncSessionLocal() as session:
        audit_count = (
            await session.execute(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "approval.requested")
            )
        ).scalar_one()
    assert audit_count == 1
    assert await agent_action_count() == 1


async def test_approve_request_enforces_permissions_and_logs_denied_action(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    from app.agents.mcp import service as mcp_service
    from app.database.models import AgentAction, AuditEvent, Workflow
    from app.database.session import AsyncSessionLocal

    document = await upload_as(
        client,
        pdf_bytes,
        "procurement",
        "researcher.alice@example.test",
        "invoice.pdf",
    )
    workflow_id = UUID(document["workflow"]["id"])
    intake_step_id = UUID(document["workflow"]["steps"][0]["id"])

    async with mcp_context("researcher.alice@example.test"):
        with pytest.raises(RuntimeError, match="Requires role"):
            await mcp_service.approve_request(workflow_id, intake_step_id)

    async with AsyncSessionLocal() as session:
        denied = (
            await session.execute(
                select(AgentAction).where(AgentAction.status == "denied")
            )
        ).scalar_one()
    assert denied.tool_name == "approve_request"

    async with mcp_context("admin.frank@example.test"):
        result = await mcp_service.approve_request(
            workflow_id,
            intake_step_id,
            "Intake review complete.",
        )

    assert result["workflow"]["current_step"] == "group_lead_approval"
    async with AsyncSessionLocal() as session:
        workflow = (
            await session.execute(select(Workflow).where(Workflow.id == workflow_id))
        ).scalar_one()
        agent_audit_count = (
            await session.execute(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "agent.approval_approved")
            )
        ).scalar_one()
    assert workflow.current_step == "group_lead_approval"
    assert agent_audit_count == 1


async def test_export_audit_log_is_admin_only(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    from app.agents.mcp import service as mcp_service
    from app.database.models import AuditEvent
    from app.database.session import AsyncSessionLocal

    document = await upload_as(
        client,
        pdf_bytes,
        "procurement",
        "researcher.alice@example.test",
        "invoice.pdf",
    )

    async with mcp_context("researcher.alice@example.test"):
        with pytest.raises(RuntimeError, match="Audit export requires"):
            await mcp_service.export_audit_log(UUID(document["id"]))

    async with mcp_context("admin.frank@example.test"):
        result = await mcp_service.export_audit_log(UUID(document["id"]))

    assert result["count"] >= 1
    assert any(event["event_type"] == "document.uploaded" for event in result["audit_events"])
    async with AsyncSessionLocal() as session:
        exported_count = (
            await session.execute(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "audit.exported")
            )
        ).scalar_one()
    assert exported_count == 1


async def test_list_pending_approvals_returns_only_decidable_steps(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    from app.agents.mcp import service as mcp_service

    document = await upload_as(
        client,
        pdf_bytes,
        "procurement",
        "researcher.alice@example.test",
        "invoice.pdf",
    )

    async with mcp_context("finance.carol@example.test"):
        finance_result = await mcp_service.list_pending_approvals()
    async with mcp_context("admin.frank@example.test"):
        admin_result = await mcp_service.list_pending_approvals()

    assert finance_result["count"] == 0
    assert admin_result["count"] == 1
    assert admin_result["approvals"][0]["workflow_id"] == document["workflow"]["id"]
