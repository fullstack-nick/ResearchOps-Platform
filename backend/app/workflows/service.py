from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.service import get_role_names
from app.core.observability import record_counter, record_event
from app.database.models import (
    Approval,
    AuditEvent,
    Document,
    User,
    Workflow,
    WorkflowStep,
)
from app.workflows.chains import WorkflowStepSpec, chain_for
from app.workflows.schemas import (
    ApprovalRead,
    DecisionRequest,
    WorkflowStateRead,
    WorkflowStepDetailRead,
)


def build_workflow_steps_for_type(
    workflow_id: uuid.UUID, workflow_type: str
) -> list[WorkflowStep]:
    chain = chain_for(workflow_type)
    if not chain:
        chain = (WorkflowStepSpec("intake_review", "operations_admin"),)
    return [
        WorkflowStep(
            id=uuid.uuid4(),
            workflow_id=workflow_id,
            step_name=spec.step_name,
            status="pending",
            assigned_role=spec.assigned_role,
            step_order=index,
        )
        for index, spec in enumerate(chain)
    ]


async def get_workflow_for_decision(
    session: AsyncSession, workflow_id: uuid.UUID
) -> Workflow:
    result = await session.execute(
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .options(
            selectinload(Workflow.steps).selectinload(WorkflowStep.approvals),
            selectinload(Workflow.document),
            selectinload(Workflow.approvals),
        )
    )
    workflow = result.scalars().unique().one_or_none()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found."
        )
    return workflow


def _first_pending_step(workflow: Workflow) -> WorkflowStep | None:
    return next(
        (step for step in workflow.steps if step.status == "pending"),
        None,
    )


def can_user_decide_step(user: User, step: WorkflowStep, document: Document) -> bool:
    roles = get_role_names(user)
    if "operations_admin" in roles or "system_admin" in roles:
        return True
    if step.assigned_role not in roles:
        return False
    if step.assigned_role == "group_lead":
        if document.research_group and document.research_group != user.research_group:
            return False
    return True


def workflow_state_view(workflow: Workflow, user: User) -> WorkflowStateRead:
    pending = _first_pending_step(workflow)
    return WorkflowStateRead(
        id=workflow.id,
        document_id=workflow.document_id,
        workflow_type=workflow.workflow_type,
        status=workflow.status,
        current_step=workflow.current_step,
        research_group=workflow.document.research_group if workflow.document else None,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        steps=[
            WorkflowStepDetailRead(
                id=step.id,
                step_name=step.step_name,
                status=step.status,
                assigned_role=step.assigned_role,
                step_order=step.step_order,
                completed_at=step.completed_at,
                created_at=step.created_at,
                approvals=[ApprovalRead.model_validate(item) for item in step.approvals],
            )
            for step in workflow.steps
        ],
        pending_step_id=pending.id if pending else None,
        can_decide_current_step=bool(
            pending and can_user_decide_step(user, pending, workflow.document)
        ),
    )


async def get_workflow_state(
    session: AsyncSession, workflow_id: uuid.UUID, user: User
) -> WorkflowStateRead:
    workflow = await get_workflow_for_decision(session, workflow_id)
    return workflow_state_view(workflow, user)


async def decide_step(
    session: AsyncSession,
    workflow_id: uuid.UUID,
    step_id: uuid.UUID,
    user: User,
    payload: DecisionRequest,
    request: Request,
) -> WorkflowStateRead:
    workflow = await get_workflow_for_decision(session, workflow_id)
    if workflow.status not in {"awaiting_review"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow is already {workflow.status}.",
        )
    step = next((item for item in workflow.steps if item.id == step_id), None)
    if step is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow step not found."
        )
    pending = _first_pending_step(workflow)
    if pending is None or pending.id != step.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This is not the current pending step for the workflow.",
        )
    if not can_user_decide_step(user, step, workflow.document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires role '{step.assigned_role}' to decide this step.",
        )
    if payload.decision == "rejected" and not (payload.reason and payload.reason.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A rejection reason is required.",
        )

    now = datetime.now(UTC)
    approval = Approval(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        workflow_step_id=step.id,
        approver_user_id=user.id,
        decision=payload.decision,
        reason=(payload.reason or None) if not payload.reason else payload.reason.strip(),
    )
    step.status = "completed"
    step.completed_at = now

    next_pending: WorkflowStep | None = None
    if payload.decision == "approved":
        next_pending = next(
            (item for item in workflow.steps if item.status == "pending"),
            None,
        )
        if next_pending is not None:
            workflow.current_step = next_pending.step_name
            workflow_event = "workflow.advanced"
            workflow_event_after: dict[str, object] = {
                "current_step": workflow.current_step,
            }
        else:
            workflow.status = "approved"
            workflow.current_step = "completed"
            workflow_event = "workflow.completed"
            workflow_event_after = {"status": "approved"}
    else:
        for remaining in workflow.steps:
            if remaining.status == "pending":
                remaining.status = "skipped"
                remaining.completed_at = now
        workflow.status = "rejected"
        workflow.current_step = step.step_name
        workflow_event = "workflow.rejected"
        workflow_event_after = {"status": "rejected", "step": step.step_name}

    session.add(approval)
    session.add(
        AuditEvent(
            actor_type="user",
            actor_id=user.id,
            document_id=workflow.document_id,
            workflow_id=workflow.id,
            event_type=(
                "approval.granted" if payload.decision == "approved" else "approval.rejected"
            ),
            after_value={
                "workflow_step_id": str(step.id),
                "step_name": step.step_name,
                "decision": payload.decision,
            },
            reason=(payload.reason or "").strip() or None,
            source_ip=request.client.host if request.client else None,
            correlation_id=request.state.correlation_id,
        )
    )
    session.add(
        AuditEvent(
            actor_type="system",
            actor_id=None,
            document_id=workflow.document_id,
            workflow_id=workflow.id,
            event_type=workflow_event,
            after_value=workflow_event_after,
            reason="Approval state machine advanced",
            source_ip=None,
            correlation_id=request.state.correlation_id,
        )
    )
    await session.commit()
    record_counter(
        "researchops.workflow.decisions",
        1,
        {
            "workflow.type": workflow.workflow_type,
            "workflow.step": step.step_name,
            "decision": payload.decision,
        },
    )
    record_event(
        "approval.granted" if payload.decision == "approved" else "approval.rejected",
        {
            "workflow.id": str(workflow.id),
            "document.id": str(workflow.document_id),
            "workflow.step": step.step_name,
            "decision": payload.decision,
        },
    )
    record_event(
        workflow_event,
        {
            "workflow.id": str(workflow.id),
            "document.id": str(workflow.document_id),
            "workflow.status": workflow.status,
            "current_step": workflow.current_step,
        },
    )
    refreshed = await get_workflow_for_decision(session, workflow.id)
    return workflow_state_view(refreshed, user)
