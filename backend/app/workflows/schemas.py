from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    workflow_step_id: UUID
    approver_user_id: UUID
    decision: str
    reason: str | None
    created_at: datetime


class WorkflowStepDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_name: str
    status: str
    assigned_role: str
    step_order: int
    completed_at: datetime | None
    created_at: datetime
    approvals: list[ApprovalRead]


class WorkflowStateRead(BaseModel):
    id: UUID
    document_id: UUID
    workflow_type: str
    status: str
    current_step: str
    research_group: str | None = None
    created_at: datetime
    updated_at: datetime
    steps: list[WorkflowStepDetailRead]
    pending_step_id: UUID | None = None
    can_decide_current_step: bool = False


class DecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=2000)
