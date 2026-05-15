from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ToolEnvelope(BaseModel):
    tool: str
    status: str = "completed"


class DocumentSearchMatch(BaseModel):
    document_id: UUID
    original_filename: str
    workflow_type: str
    status: str
    research_group: str | None
    created_at: datetime
    score: int
    matched_fields: list[str] = Field(default_factory=list)
    matched_chunks: list[str] = Field(default_factory=list)


class SearchDocumentsResult(ToolEnvelope):
    query: str
    count: int
    documents: list[DocumentSearchMatch]


class DocumentSummaryResult(ToolEnvelope):
    document: dict[str, Any]
    workflow: dict[str, Any]
    extraction: dict[str, Any]
    indexing: dict[str, Any]
    recent_audit_events: list[dict[str, Any]]


class DocumentFieldsResult(ToolEnvelope):
    document_id: UUID
    available: bool
    extraction_status: str
    fields: list[dict[str, Any]]
    line_items: list[dict[str, Any]]


class MissingFieldsResult(ToolEnvelope):
    document_id: UUID
    available: bool
    extraction_status: str
    missing_fields: list[str]


class CompareDocumentsResult(ToolEnvelope):
    left_document_id: UUID
    right_document_id: UUID
    field_differences: list[dict[str, Any]]
    line_item_total_difference: float | None


class WorkflowStatusResult(ToolEnvelope):
    workflow: dict[str, Any]


class PendingApproval(BaseModel):
    workflow_id: UUID
    document_id: UUID
    document_name: str
    workflow_type: str
    step_id: UUID
    step_name: str
    assigned_role: str
    research_group: str | None
    created_at: datetime


class PendingApprovalsResult(ToolEnvelope):
    count: int
    approvals: list[PendingApproval]


class AuditExportResult(ToolEnvelope):
    count: int
    audit_events: list[dict[str, Any]]


class DeterministicTaskResult(ToolEnvelope):
    model_config = ConfigDict(extra="allow")

    available: bool
    count: int
    items: list[dict[str, Any]]
    message: str | None = None
