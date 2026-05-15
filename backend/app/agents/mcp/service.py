from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, cast

from fastapi import HTTPException, Request, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.mcp.auth import McpAuthContext, get_mcp_auth_context
from app.agents.mcp.schemas import (
    AuditExportResult,
    CompareDocumentsResult,
    DeterministicTaskResult,
    DocumentFieldsResult,
    DocumentSearchMatch,
    DocumentSummaryResult,
    MissingFieldsResult,
    PendingApproval,
    PendingApprovalsResult,
    SearchDocumentsResult,
    WorkflowStatusResult,
)
from app.auth.access import assert_document_access, document_visibility_filter, is_admin
from app.core.config import get_settings
from app.core.observability import record_counter, record_event, record_histogram
from app.database.models import (
    AgentAction,
    AuditEvent,
    Document,
    DocumentChunk,
    ExtractionRun,
    IndexingRun,
    User,
    Workflow,
    WorkflowStep,
)
from app.database.session import AsyncSessionLocal
from app.extraction.service import get_document_extraction
from app.workflows.schemas import DecisionRequest
from app.workflows.service import (
    can_user_decide_step,
    decide_step,
    get_workflow_for_decision,
    workflow_state_view,
)

JsonDict = dict[str, Any]
ToolOperation = Callable[[AsyncSession, McpAuthContext], Awaitable[JsonDict]]

SENSITIVE_ARGUMENT_PARTS = ("token", "secret", "password", "key", "authorization")
SUMMARY_LIST_LIMIT = 5


@dataclass(frozen=True)
class _Client:
    host: str | None


@dataclass(frozen=True)
class _State:
    correlation_id: str


@dataclass(frozen=True)
class _AgentRequest:
    client: _Client
    state: _State


async def execute_tool(
    tool_name: str,
    arguments: JsonDict,
    operation: ToolOperation,
) -> JsonDict:
    context = get_mcp_auth_context()
    started = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            result = await operation(session, context)
            await _write_agent_action(
                session=session,
                context=context,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                status_value="completed",
                error_message=None,
                duration_ms=_duration_ms(started),
            )
            await session.commit()
            duration_ms = _duration_ms(started)
            _record_agent_tool_metrics(tool_name, "completed", duration_ms, context, result)
            return result
    except HTTPException as exc:
        await _record_error(tool_name, arguments, context, started, exc)
        raise RuntimeError(str(exc.detail)) from exc
    except Exception as exc:
        await _record_error(tool_name, arguments, context, started, exc)
        raise


async def search_documents(
    query: str,
    workflow_type: str | None = None,
    limit: int | None = None,
) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        max_results = _limit(limit)
        statement = _visible_documents_statement(context.delegated_user).options(
            selectinload(Document.extracted_fields),
            selectinload(Document.workflow),
        )
        if workflow_type:
            statement = statement.where(Document.workflow_type == workflow_type)
        statement = statement.order_by(Document.created_at.desc()).limit(max_results * 4)
        documents = list((await session.execute(statement)).scalars().unique().all())
        chunks = await _chunks_by_document(session, [item.id for item in documents])
        matches = [
            _score_document_match(document, chunks.get(document.id, []), query)
            for document in documents
        ]
        filtered = [
            item for item in matches if not query.strip() or item.score > 0
        ][:max_results]
        result = SearchDocumentsResult(
            tool="search_documents",
            query=query,
            count=len(filtered),
            documents=filtered,
        )
        return result.model_dump(mode="json")

    return await execute_tool(
        "search_documents",
        {"query": query, "workflow_type": workflow_type, "limit": limit},
        _operation,
    )


async def get_document_summary(document_id: uuid.UUID) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        document = await _load_document(session, document_id, context.delegated_user)
        latest_extraction = await _latest_extraction_run(session, document.id)
        latest_indexing = await _latest_indexing_run(session, document.id)
        recent_events = await _recent_audit_events(session, document.id, limit=5)
        workflow = workflow_state_view(document.workflow, context.delegated_user)
        result = DocumentSummaryResult(
            tool="get_document_summary",
            document={
                "id": str(document.id),
                "original_filename": document.original_filename,
                "workflow_type": document.workflow_type,
                "status": document.status,
                "research_group": document.research_group,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
            },
            workflow=workflow.model_dump(mode="json"),
            extraction=_extraction_summary(latest_extraction),
            indexing=_indexing_summary(latest_indexing),
            recent_audit_events=recent_events,
        )
        return result.model_dump(mode="json")

    return await execute_tool(
        "get_document_summary",
        {"document_id": str(document_id)},
        _operation,
    )


async def get_document_fields(document_id: uuid.UUID) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        await _load_document(session, document_id, context.delegated_user)
        extraction = await get_document_extraction(session, document_id)
        result = DocumentFieldsResult(
            tool="get_document_fields",
            document_id=document_id,
            available=extraction.available,
            extraction_status=extraction.status,
            fields=[field.model_dump(mode="json") for field in extraction.fields],
            line_items=[item.model_dump(mode="json") for item in extraction.line_items],
        )
        return result.model_dump(mode="json")

    return await execute_tool(
        "get_document_fields",
        {"document_id": str(document_id)},
        _operation,
    )


async def list_missing_fields(document_id: uuid.UUID) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        await _load_document(session, document_id, context.delegated_user)
        extraction = await get_document_extraction(session, document_id)
        result = MissingFieldsResult(
            tool="list_missing_fields",
            document_id=document_id,
            available=extraction.available,
            extraction_status=extraction.status,
            missing_fields=extraction.missing_fields,
        )
        return result.model_dump(mode="json")

    return await execute_tool(
        "list_missing_fields",
        {"document_id": str(document_id)},
        _operation,
    )


async def compare_documents(
    left_document_id: uuid.UUID, right_document_id: uuid.UUID
) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        await _load_document(session, left_document_id, context.delegated_user)
        await _load_document(session, right_document_id, context.delegated_user)
        left_fields = await _latest_field_map(session, left_document_id)
        right_fields = await _latest_field_map(session, right_document_id)
        keys = sorted(set(left_fields) | set(right_fields))
        differences = [
            {
                "field_key": key,
                "left_value": left_fields.get(key),
                "right_value": right_fields.get(key),
            }
            for key in keys
            if left_fields.get(key) != right_fields.get(key)
        ]
        result = CompareDocumentsResult(
            tool="compare_documents",
            left_document_id=left_document_id,
            right_document_id=right_document_id,
            field_differences=differences,
            line_item_total_difference=(
                await _line_item_total(session, left_document_id)
            )
            - (await _line_item_total(session, right_document_id)),
        )
        return result.model_dump(mode="json")

    return await execute_tool(
        "compare_documents",
        {
            "left_document_id": str(left_document_id),
            "right_document_id": str(right_document_id),
        },
        _operation,
    )


async def get_workflow_status(workflow_id: uuid.UUID) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        workflow = await _load_workflow(session, workflow_id, context.delegated_user)
        result = WorkflowStatusResult(
            tool="get_workflow_status",
            workflow=workflow_state_view(workflow, context.delegated_user).model_dump(
                mode="json"
            ),
        )
        return result.model_dump(mode="json")

    return await execute_tool(
        "get_workflow_status",
        {"workflow_id": str(workflow_id)},
        _operation,
    )


async def list_pending_approvals(limit: int | None = None) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        max_results = _limit(limit)
        statement = (
            select(Workflow)
            .join(Document, Workflow.document_id == Document.id)
            .options(
                selectinload(Workflow.document),
                selectinload(Workflow.steps).selectinload(WorkflowStep.approvals),
            )
            .where(Workflow.status == "awaiting_review")
            .order_by(Workflow.created_at.desc())
        )
        visibility = document_visibility_filter(context.delegated_user)
        if visibility is not None:
            statement = statement.where(visibility)
        workflows = list(
            (await session.execute(statement.limit(max_results * 4)))
            .scalars()
            .unique()
            .all()
        )
        approvals: list[PendingApproval] = []
        for workflow in workflows:
            pending = _first_pending_step(workflow)
            if pending and can_user_decide_step(
                context.delegated_user, pending, workflow.document
            ):
                approvals.append(
                    PendingApproval(
                        workflow_id=workflow.id,
                        document_id=workflow.document_id,
                        document_name=workflow.document.original_filename,
                        workflow_type=workflow.workflow_type,
                        step_id=pending.id,
                        step_name=pending.step_name,
                        assigned_role=pending.assigned_role,
                        research_group=workflow.document.research_group,
                        created_at=workflow.created_at,
                    )
                )
            if len(approvals) >= max_results:
                break
        result = PendingApprovalsResult(
            tool="list_pending_approvals",
            count=len(approvals),
            approvals=approvals,
        )
        return result.model_dump(mode="json")

    return await execute_tool(
        "list_pending_approvals",
        {"limit": limit},
        _operation,
    )


async def create_approval_request(
    workflow_id: uuid.UUID, reason: str | None = None
) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        workflow = await _load_workflow(session, workflow_id, context.delegated_user)
        pending = _first_pending_step(workflow)
        if pending is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workflow has no pending approval step.",
            )
        event = AuditEvent(
            actor_type="agent",
            actor_id=context.agent_user.id,
            document_id=workflow.document_id,
            workflow_id=workflow.id,
            event_type="approval.requested",
            after_value={
                "workflow_step_id": str(pending.id),
                "step_name": pending.step_name,
                "assigned_role": pending.assigned_role,
                "delegated_user_id": str(context.delegated_user.id),
            },
            reason=_clean_reason(reason) or "MCP agent requested approval review",
            source_ip=context.source_ip,
            correlation_id=context.correlation_id,
        )
        session.add(event)
        result = {
            "tool": "create_approval_request",
            "status": "completed",
            "workflow_id": str(workflow.id),
            "document_id": str(workflow.document_id),
            "pending_step_id": str(pending.id),
            "pending_step": pending.step_name,
            "assigned_role": pending.assigned_role,
        }
        return result

    return await execute_tool(
        "create_approval_request",
        {"workflow_id": str(workflow_id), "reason": reason},
        _operation,
    )


async def approve_request(
    workflow_id: uuid.UUID, step_id: uuid.UUID, reason: str | None = None
) -> JsonDict:
    return await _decide_request(workflow_id, step_id, "approved", reason)


async def reject_request(workflow_id: uuid.UUID, step_id: uuid.UUID, reason: str) -> JsonDict:
    return await _decide_request(workflow_id, step_id, "rejected", reason)


async def export_audit_log(
    document_id: uuid.UUID | None = None,
    event_type: str | None = None,
    limit: int | None = None,
) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        if not is_admin(context.delegated_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Audit export requires an admin role.",
            )
        max_results = _limit(limit)
        statement = select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(max_results)
        if document_id:
            statement = statement.where(AuditEvent.document_id == document_id)
        if event_type:
            statement = statement.where(AuditEvent.event_type == event_type)
        events = list((await session.execute(statement)).scalars().all())
        session.add(
            AuditEvent(
                actor_type="agent",
                actor_id=context.agent_user.id,
                document_id=document_id,
                workflow_id=None,
                event_type="audit.exported",
                after_value={
                    "event_count": len(events),
                    "event_type": event_type,
                    "delegated_user_id": str(context.delegated_user.id),
                },
                reason="MCP agent exported audit log",
                source_ip=context.source_ip,
                correlation_id=context.correlation_id,
            )
        )
        result = AuditExportResult(
            tool="export_audit_log",
            count=len(events),
            audit_events=[_audit_event_dict(item) for item in events],
        )
        return result.model_dump(mode="json")

    return await execute_tool(
        "export_audit_log",
        {
            "document_id": str(document_id) if document_id else None,
            "event_type": event_type,
            "limit": limit,
        },
        _operation,
    )


async def create_onboarding_tasks(document_id: uuid.UUID) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        document = await _load_document(session, document_id, context.delegated_user)
        if document.workflow_type != "hr_onboarding":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Onboarding task creation requires an HR onboarding document.",
            )
        tasks = await _task_items_from_fields(session, document.id, "onboarding")
        result = DeterministicTaskResult(
            tool="create_onboarding_tasks",
            available=bool(tasks),
            count=len(tasks),
            items=tasks,
            message=None
            if tasks
            else "No onboarding extraction fields are available for this Phase 5 demo.",
        )
        return result.model_dump(mode="json")

    return await execute_tool(
        "create_onboarding_tasks",
        {"document_id": str(document_id)},
        _operation,
    )


async def list_contracts_expiring_soon(days: int = 90) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        cutoff = datetime.now(UTC).date() + timedelta(days=days)
        statement = _visible_documents_statement(context.delegated_user).where(
            Document.workflow_type == "contracts"
        )
        documents = list((await session.execute(statement)).scalars().unique().all())
        items: list[dict[str, Any]] = []
        for document in documents:
            fields = await _latest_field_map(session, document.id)
            expiry = fields.get("expiry_date") or fields.get("contract_end_date")
            if not expiry:
                continue
            parsed = _parse_date(str(expiry))
            if parsed and parsed <= cutoff:
                items.append(
                    {
                        "document_id": str(document.id),
                        "document_name": document.original_filename,
                        "expiry_date": parsed.isoformat(),
                    }
                )
        result = DeterministicTaskResult(
            tool="list_contracts_expiring_soon",
            available=bool(items),
            count=len(items),
            items=items,
            message=None
            if items
            else "No contract expiry extraction fields are available for this Phase 5 demo.",
        )
        return result.model_dump(mode="json")

    return await execute_tool(
        "list_contracts_expiring_soon",
        {"days": days},
        _operation,
    )


async def get_grant_deadlines(days: int = 120) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        cutoff = datetime.now(UTC).date() + timedelta(days=days)
        statement = _visible_documents_statement(context.delegated_user).where(
            Document.workflow_type == "grants"
        )
        documents = list((await session.execute(statement)).scalars().unique().all())
        items: list[dict[str, Any]] = []
        for document in documents:
            fields = await _latest_field_map(session, document.id)
            for key in ("reporting_deadline", "next_report_due", "end_date"):
                value = fields.get(key)
                parsed = _parse_date(str(value)) if value else None
                if parsed and parsed <= cutoff:
                    items.append(
                        {
                            "document_id": str(document.id),
                            "document_name": document.original_filename,
                            "field_key": key,
                            "deadline": parsed.isoformat(),
                        }
                    )
        result = DeterministicTaskResult(
            tool="get_grant_deadlines",
            available=bool(items),
            count=len(items),
            items=items,
            message=None
            if items
            else "No grant deadline extraction fields are available for this Phase 5 demo.",
        )
        return result.model_dump(mode="json")

    return await execute_tool(
        "get_grant_deadlines",
        {"days": days},
        _operation,
    )


async def _decide_request(
    workflow_id: uuid.UUID,
    step_id: uuid.UUID,
    decision: str,
    reason: str | None,
) -> JsonDict:
    async def _operation(session: AsyncSession, context: McpAuthContext) -> JsonDict:
        workflow = await _load_workflow(session, workflow_id, context.delegated_user)
        request = cast(
            Request,
            _AgentRequest(
                client=_Client(host=context.source_ip),
                state=_State(correlation_id=context.correlation_id),
            ),
        )
        state_view = await decide_step(
            session=session,
            workflow_id=workflow.id,
            step_id=step_id,
            user=context.delegated_user,
            payload=DecisionRequest(
                decision=cast(Literal["approved", "rejected"], decision),
                reason=reason,
            ),
            request=request,
        )
        session.add(
            AuditEvent(
                actor_type="agent",
                actor_id=context.agent_user.id,
                document_id=state_view.document_id,
                workflow_id=workflow.id,
                event_type=f"agent.approval_{decision}",
                after_value={
                    "workflow_step_id": str(step_id),
                    "decision": decision,
                    "delegated_user_id": str(context.delegated_user.id),
                },
                reason=_clean_reason(reason) or f"MCP agent submitted {decision}",
                source_ip=context.source_ip,
                correlation_id=context.correlation_id,
            )
        )
        return {
            "tool": "approve_request" if decision == "approved" else "reject_request",
            "status": "completed",
            "workflow": state_view.model_dump(mode="json"),
        }

    return await execute_tool(
        "approve_request" if decision == "approved" else "reject_request",
        {"workflow_id": str(workflow_id), "step_id": str(step_id), "reason": reason},
        _operation,
    )


async def _record_error(
    tool_name: str,
    arguments: JsonDict,
    context: McpAuthContext,
    started: float,
    exc: Exception,
) -> None:
    status_value = "failed"
    error_message = str(exc)
    if isinstance(exc, HTTPException):
        error_message = str(exc.detail)
        if exc.status_code in {
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        }:
            status_value = "denied"
    async with AsyncSessionLocal() as session:
        await _write_agent_action(
            session=session,
            context=context,
            tool_name=tool_name,
            arguments=arguments,
            result=None,
            status_value=status_value,
            error_message=error_message,
            duration_ms=_duration_ms(started),
        )
        await session.commit()
    _record_agent_tool_metrics(tool_name, status_value, _duration_ms(started), context, None)


async def _write_agent_action(
    session: AsyncSession,
    context: McpAuthContext,
    tool_name: str,
    arguments: JsonDict,
    result: JsonDict | None,
    status_value: str,
    error_message: str | None,
    duration_ms: int,
) -> None:
    session.add(
        AgentAction(
            id=uuid.uuid4(),
            tool_name=tool_name,
            agent_user_id=context.agent_user.id,
            agent_name=context.agent_name,
            delegated_user_id=context.delegated_user.id,
            document_id=_uuid_arg(arguments, "document_id", "left_document_id"),
            workflow_id=_uuid_arg(arguments, "workflow_id"),
            arguments=_sanitize_arguments(arguments),
            result_summary=_summarize_result(result),
            status=status_value,
            error_message=error_message,
            duration_ms=duration_ms,
            correlation_id=context.correlation_id,
        )
    )


def _visible_documents_statement(user: User) -> Select[tuple[Document]]:
    statement = select(Document).options(selectinload(Document.workflow))
    visibility = document_visibility_filter(user)
    if visibility is not None:
        statement = statement.where(visibility)
    return statement


async def _load_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    user: User,
) -> Document:
    result = await session.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.workflow).selectinload(Workflow.steps).selectinload(
                WorkflowStep.approvals
            ),
            selectinload(Document.extraction_runs),
        )
    )
    document = result.scalars().unique().one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    assert_document_access(user, document)
    return document


async def _load_workflow(
    session: AsyncSession,
    workflow_id: uuid.UUID,
    user: User,
) -> Workflow:
    workflow = await get_workflow_for_decision(session, workflow_id)
    assert_document_access(user, workflow.document)
    return workflow


async def _latest_extraction_run(
    session: AsyncSession, document_id: uuid.UUID
) -> ExtractionRun | None:
    result = await session.execute(
        select(ExtractionRun)
        .where(ExtractionRun.document_id == document_id)
        .options(selectinload(ExtractionRun.fields), selectinload(ExtractionRun.line_items))
        .order_by(ExtractionRun.created_at.desc(), ExtractionRun.id.desc())
        .limit(1)
    )
    return result.scalars().unique().one_or_none()


async def _latest_indexing_run(
    session: AsyncSession, document_id: uuid.UUID
) -> IndexingRun | None:
    result = await session.execute(
        select(IndexingRun)
        .where(IndexingRun.document_id == document_id)
        .options(selectinload(IndexingRun.chunks))
        .order_by(IndexingRun.created_at.desc(), IndexingRun.id.desc())
        .limit(1)
    )
    return result.scalars().unique().one_or_none()


async def _chunks_by_document(
    session: AsyncSession, document_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[DocumentChunk]]:
    if not document_ids:
        return {}
    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id.in_(document_ids))
        .order_by(DocumentChunk.chunk_index)
    )
    chunks_by_document: dict[uuid.UUID, list[DocumentChunk]] = {}
    for chunk in result.scalars().all():
        chunks_by_document.setdefault(chunk.document_id, []).append(chunk)
    return chunks_by_document


def _score_document_match(
    document: Document, chunks: list[DocumentChunk], query: str
) -> DocumentSearchMatch:
    terms = [term for term in query.lower().split() if term]
    haystacks = [
        document.original_filename,
        document.workflow_type,
        document.status,
        document.research_group or "",
    ]
    matched_fields: list[str] = []
    for field in document.extracted_fields:
        text = " ".join(
            part
            for part in (
                field.field_key,
                field.label,
                field.display_value or "",
            )
            if part
        )
        haystacks.append(text)
        if _contains_any(text, terms):
            matched_fields.append(field.field_key)
    matched_chunks = [
        _snippet(chunk.content, terms)
        for chunk in chunks
        if _contains_any(chunk.content, terms)
    ][:3]
    score = sum(1 for text in haystacks if _contains_any(text, terms)) + len(matched_chunks)
    if not terms:
        score = 1
    return DocumentSearchMatch(
        document_id=document.id,
        original_filename=document.original_filename,
        workflow_type=document.workflow_type,
        status=document.status,
        research_group=document.research_group,
        created_at=document.created_at,
        score=score,
        matched_fields=matched_fields[:5],
        matched_chunks=matched_chunks,
    )


def _contains_any(value: str, terms: list[str]) -> bool:
    lowered = value.lower()
    return any(term in lowered for term in terms)


def _snippet(value: str, terms: list[str]) -> str:
    if not terms:
        return value[:240]
    lowered = value.lower()
    first_index = min(
        (lowered.find(term) for term in terms if term in lowered),
        default=0,
    )
    start = max(first_index - 80, 0)
    return value[start : start + 240]


async def _latest_field_map(
    session: AsyncSession, document_id: uuid.UUID
) -> dict[str, str | None]:
    run = await _latest_extraction_run(session, document_id)
    if run is None:
        return {}
    return {field.field_key: field.display_value for field in run.fields}


async def _line_item_total(session: AsyncSession, document_id: uuid.UUID) -> float:
    run = await _latest_extraction_run(session, document_id)
    if run is None:
        return 0.0
    return float(sum(item.amount or 0.0 for item in run.line_items))


async def _task_items_from_fields(
    session: AsyncSession, document_id: uuid.UUID, category: str
) -> list[dict[str, Any]]:
    fields = await _latest_field_map(session, document_id)
    items: list[dict[str, Any]] = []
    for key, value in fields.items():
        if value and key.startswith(("required_", "mandatory_", "missing_")):
            items.append({"category": category, "field_key": key, "value": value})
    return items


def _first_pending_step(workflow: Workflow) -> WorkflowStep | None:
    return next((step for step in workflow.steps if step.status == "pending"), None)


def _extraction_summary(run: ExtractionRun | None) -> dict[str, Any]:
    if run is None:
        return {"status": "not_requested", "missing_fields": [], "latest_run_id": None}
    return {
        "status": run.status,
        "latest_run_id": str(run.id),
        "missing_fields": run.missing_fields,
        "missing_field_count": len(run.missing_fields),
    }


def _indexing_summary(run: IndexingRun | None) -> dict[str, Any]:
    if run is None:
        return {"status": "not_requested", "latest_run_id": None, "chunk_count": 0}
    return {
        "status": run.status,
        "latest_run_id": str(run.id),
        "chunk_count": run.chunk_count,
    }


async def _recent_audit_events(
    session: AsyncSession, document_id: uuid.UUID, limit: int
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(AuditEvent)
        .where(AuditEvent.document_id == document_id)
        .order_by(AuditEvent.timestamp.desc())
        .limit(limit)
    )
    return [_audit_event_dict(item) for item in result.scalars().all()]


def _audit_event_dict(event: AuditEvent) -> dict[str, Any]:
    return {
        "event_id": str(event.event_id),
        "timestamp": event.timestamp.isoformat(),
        "actor_type": event.actor_type,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "document_id": str(event.document_id) if event.document_id else None,
        "workflow_id": str(event.workflow_id) if event.workflow_id else None,
        "event_type": event.event_type,
        "before_value": event.before_value,
        "after_value": event.after_value,
        "reason": event.reason,
        "correlation_id": event.correlation_id,
    }


def _sanitize_arguments(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in cast(dict[str, Any], value).items():
            if any(part in key.lower() for part in SENSITIVE_ARGUMENT_PARTS):
                clean[key] = "[redacted]"
            else:
                clean[key] = _sanitize_arguments(item)
        return clean
    if isinstance(value, list):
        return [
            _sanitize_arguments(item)
            for item in cast(list[Any], value)[:SUMMARY_LIST_LIMIT]
        ]
    if isinstance(value, str):
        return value if len(value) <= 500 else f"{value[:500]}..."
    return value


def _summarize_result(result: JsonDict | None) -> dict[str, Any] | None:
    if result is None:
        return None
    summary: dict[str, Any] = {}
    for key in (
        "tool",
        "status",
        "count",
        "available",
        "document_id",
        "workflow_id",
        "pending_step",
    ):
        if key in result:
            summary[key] = result[key]
    for key, value in result.items():
        if isinstance(value, list):
            summary[f"{key}_count"] = len(cast(list[Any], value))
        elif isinstance(value, dict) and key in {"document", "workflow", "extraction"}:
            summary[key] = value
    return summary or {"keys": sorted(result.keys())[:SUMMARY_LIST_LIMIT]}


def _uuid_arg(arguments: JsonDict, *keys: str) -> uuid.UUID | None:
    for key in keys:
        value = arguments.get(key)
        if not value:
            continue
        try:
            return uuid.UUID(str(value))
        except ValueError:
            return None
    return None


def _limit(limit: int | None) -> int:
    max_results = get_settings().mcp_max_results
    return max(1, min(limit or max_results, max_results))


def _duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _record_agent_tool_metrics(
    tool_name: str,
    status_value: str,
    duration_ms: int,
    context: McpAuthContext,
    result: JsonDict | None,
) -> None:
    attributes = {
        "mcp.tool": tool_name,
        "mcp.status": status_value,
        "agent.name": context.agent_name,
        "delegated_user.id": str(context.delegated_user.id),
    }
    record_counter("researchops.agent.tool_calls", 1, attributes)
    record_histogram("researchops.agent.tool_duration_ms", duration_ms, attributes)
    if result is not None and "count" in result:
        record_histogram("researchops.agent.tool_result_count", int(result["count"]), attributes)
    record_event(
        "agent.tool_call",
        {
            "mcp.tool": tool_name,
            "mcp.status": status_value,
            "duration_ms": duration_ms,
        },
    )


def _clean_reason(reason: str | None) -> str | None:
    if not reason:
        return None
    cleaned = reason.strip()
    return cleaned or None


def _parse_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value.strip()).date()
    except ValueError:
        return None
