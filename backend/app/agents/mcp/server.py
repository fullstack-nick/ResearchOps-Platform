from __future__ import annotations

import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.agents.mcp import service
from app.core.config import get_settings


def create_mcp_server() -> FastMCP:
    settings = get_settings()
    mcp = FastMCP(
        settings.mcp_server_name,
        instructions=(
            "Controlled tools for ResearchOps document search, extraction review, "
            "workflow approvals, and audit exports. All calls are permission-checked "
            "against the delegated ResearchOps user."
        ),
        host="0.0.0.0",  # noqa: S104
        port=8002,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
    )

    @mcp.tool(
        description=(
            "Search documents visible to the delegated user by filename, workflow type, "
            "extracted field content, and indexed document chunks."
        )
    )
    async def search_documents(
        query: str,
        workflow_type: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return await service.search_documents(query, workflow_type, limit)

    @mcp.tool(
        description=(
            "Get document metadata, workflow state, extraction/indexing status, "
            "and recent audit events."
        )
    )
    async def get_document_summary(document_id: uuid.UUID) -> dict[str, Any]:
        return await service.get_document_summary(document_id)

    @mcp.tool(
        description=(
            "Get extracted fields, corrected values, confidence values, source pages, "
            "and line items."
        )
    )
    async def get_document_fields(document_id: uuid.UUID) -> dict[str, Any]:
        return await service.get_document_fields(document_id)

    @mcp.tool(description="List missing required fields from the latest extraction run.")
    async def list_missing_fields(document_id: uuid.UUID) -> dict[str, Any]:
        return await service.list_missing_fields(document_id)

    @mcp.tool(
        description=(
            "Compare extracted fields and line-item totals between two accessible "
            "documents."
        )
    )
    async def compare_documents(
        left_document_id: uuid.UUID,
        right_document_id: uuid.UUID,
    ) -> dict[str, Any]:
        return await service.compare_documents(left_document_id, right_document_id)

    @mcp.tool(
        description=(
            "Get workflow status, approval chain, approval history, "
            "and delegated-user decidability."
        )
    )
    async def get_workflow_status(workflow_id: uuid.UUID) -> dict[str, Any]:
        return await service.get_workflow_status(workflow_id)

    @mcp.tool(description="List currently pending approval steps the delegated user can decide.")
    async def list_pending_approvals(limit: int | None = None) -> dict[str, Any]:
        return await service.list_pending_approvals(limit)

    @mcp.tool(
        description=(
            "Record an agent-created approval request for the current pending "
            "workflow step."
        )
    )
    async def create_approval_request(
        workflow_id: uuid.UUID,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return await service.create_approval_request(workflow_id, reason)

    @mcp.tool(
        description=(
            "Approve the current pending workflow step when the delegated user has "
            "permission."
        )
    )
    async def approve_request(
        workflow_id: uuid.UUID,
        step_id: uuid.UUID,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return await service.approve_request(workflow_id, step_id, reason)

    @mcp.tool(
        description=(
            "Reject the current pending workflow step when the delegated user has "
            "permission."
        )
    )
    async def reject_request(
        workflow_id: uuid.UUID,
        step_id: uuid.UUID,
        reason: str,
    ) -> dict[str, Any]:
        return await service.reject_request(workflow_id, step_id, reason)

    @mcp.tool(description="Export audit events as structured JSON. Admin role required.")
    async def export_audit_log(
        document_id: uuid.UUID | None = None,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return await service.export_audit_log(document_id, event_type, limit)

    @mcp.tool(
        description=(
            "Create deterministic onboarding task suggestions from available HR "
            "extraction fields."
        )
    )
    async def create_onboarding_tasks(document_id: uuid.UUID) -> dict[str, Any]:
        return await service.create_onboarding_tasks(document_id)

    @mcp.tool(
        description=(
            "List accessible contracts with extracted expiry dates within the "
            "requested horizon."
        )
    )
    async def list_contracts_expiring_soon(days: int = 90) -> dict[str, Any]:
        return await service.list_contracts_expiring_soon(days)

    @mcp.tool(
        description=(
            "List accessible grant documents with extracted deadlines within the "
            "requested horizon."
        )
    )
    async def get_grant_deadlines(days: int = 120) -> dict[str, Any]:
        return await service.get_grant_deadlines(days)

    return mcp
