from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.schemas import AuditEventListResponse, AuditEventRead
from app.auth.access import (
    assert_document_access,
    document_visibility_filter,
    is_admin,
)
from app.auth.dependencies import CurrentUserDep
from app.auth.schemas import (
    AuthConfigRead,
    CurrentUserRead,
    DevUserListResponse,
    DevUserOption,
)
from app.auth.service import get_active_users_with_roles, get_role_names
from app.core.config import get_settings
from app.dashboard.schemas import DashboardSummary, QueueCount
from app.database.models import AuditEvent, Document, ExtractionRun, User, Workflow
from app.database.session import get_session
from app.documents.schemas import DocumentListResponse, DocumentRead, UploadResponse
from app.documents.service import (
    create_document_upload,
    get_document,
    get_document_file_bytes,
    list_documents,
)
from app.extraction.schemas import ExtractedFieldRead, ExtractionResponse, FieldCorrectionRequest
from app.extraction.service import (
    correct_extracted_field,
    get_document_extraction,
    retry_extraction,
)
from app.search.schemas import (
    IndexingResponse,
    QuestionAnswerRead,
    QuestionListResponse,
    QuestionRequest,
)
from app.search.service import (
    answer_document_question,
    get_document_indexing,
    list_document_questions,
    retry_indexing,
)
from app.workflows.schemas import DecisionRequest, WorkflowStateRead
from app.workflows.service import decide_step, get_workflow_state

router = APIRouter()


async def _load_authorized_document(
    session: AsyncSession, document_id: UUID, user: User
) -> Document:
    document = await get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    assert_document_access(user, document)
    return document


@router.get("/auth/me", response_model=CurrentUserRead)
async def auth_me(user: CurrentUserDep) -> CurrentUserRead:
    return CurrentUserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        research_group=user.research_group,
        is_active=user.is_active,
        roles=sorted(get_role_names(user)),
    )


@router.get("/auth/config", response_model=AuthConfigRead)
async def auth_config() -> AuthConfigRead:
    settings = get_settings()
    return AuthConfigRead(
        auth_mode=settings.auth_mode,
        entra_client_id=settings.entra_client_id,
        entra_authority=settings.entra_authority,
        entra_required_scope=settings.entra_required_scope,
    )


@router.get("/auth/dev-users", response_model=DevUserListResponse)
async def auth_dev_users(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DevUserListResponse:
    settings = get_settings()
    if settings.is_entra_auth:
        return DevUserListResponse(users=[])
    users = await get_active_users_with_roles(session)
    return DevUserListResponse(
        users=[
            DevUserOption(
                email=user.email,
                display_name=user.display_name,
                research_group=user.research_group,
                roles=sorted(get_role_names(user)),
            )
            for user in users
        ]
    )


@router.post("/documents", response_model=UploadResponse, status_code=201)
async def upload_document(
    request: Request,
    workflow_type: Annotated[str, Query()],
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> UploadResponse:
    document = await create_document_upload(session, file, workflow_type, request, user)
    return UploadResponse(document=DocumentRead.model_validate(document))


@router.get("/documents", response_model=DocumentListResponse)
async def documents(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
    workflow_type: str | None = None,
    status: str | None = None,
) -> DocumentListResponse:
    rows = await list_documents(
        session, user=user, workflow_type=workflow_type, status_filter=status
    )
    return DocumentListResponse(documents=[DocumentRead.model_validate(row) for row in rows])


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def document_detail(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> DocumentRead:
    document = await _load_authorized_document(session, document_id, user)
    return DocumentRead.model_validate(document)


@router.get("/documents/{document_id}/file")
async def document_file(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> Response:
    await _load_authorized_document(session, document_id, user)
    document, content = await get_document_file_bytes(session, document_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Cache-Control": "private, max-age=60",
            "Content-Disposition": f'inline; filename="{document.safe_filename}"',
        },
    )


@router.get("/documents/{document_id}/extraction", response_model=ExtractionResponse)
async def document_extraction(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> ExtractionResponse:
    await _load_authorized_document(session, document_id, user)
    return await get_document_extraction(session, document_id)


@router.post("/documents/{document_id}/extraction/retry", response_model=ExtractionResponse)
async def retry_document_extraction(
    document_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> ExtractionResponse:
    await _load_authorized_document(session, document_id, user)
    return await retry_extraction(session, document_id, request, user)


@router.patch("/documents/{document_id}/fields/{field_id}", response_model=ExtractedFieldRead)
async def correct_document_field(
    document_id: UUID,
    field_id: UUID,
    payload: FieldCorrectionRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> ExtractedFieldRead:
    await _load_authorized_document(session, document_id, user)
    return await correct_extracted_field(session, document_id, field_id, payload, request, user)


@router.get("/documents/{document_id}/indexing", response_model=IndexingResponse)
async def document_indexing(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> IndexingResponse:
    await _load_authorized_document(session, document_id, user)
    return await get_document_indexing(session, document_id)


@router.post("/documents/{document_id}/indexing/retry", response_model=IndexingResponse)
async def retry_document_indexing(
    document_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> IndexingResponse:
    await _load_authorized_document(session, document_id, user)
    return await retry_indexing(session, document_id, request, user)


@router.post(
    "/documents/{document_id}/questions",
    response_model=QuestionAnswerRead,
    status_code=201,
)
async def ask_document_question(
    document_id: UUID,
    payload: QuestionRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> QuestionAnswerRead:
    await _load_authorized_document(session, document_id, user)
    record = await answer_document_question(
        session, document_id, payload.question, request, user
    )
    return QuestionAnswerRead.model_validate(record)


@router.get("/documents/{document_id}/questions", response_model=QuestionListResponse)
async def document_questions(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> QuestionListResponse:
    await _load_authorized_document(session, document_id, user)
    records = await list_document_questions(session, document_id)
    return QuestionListResponse(
        questions=[QuestionAnswerRead.model_validate(record) for record in records]
    )


@router.get("/workflows/{workflow_id}", response_model=WorkflowStateRead)
async def workflow_detail(
    workflow_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> WorkflowStateRead:
    state = await get_workflow_state(session, workflow_id, user)
    assert_document_access(
        user,
        await _load_document_for_workflow(session, state.document_id),
    )
    return state


async def _load_document_for_workflow(
    session: AsyncSession, document_id: UUID
) -> Document:
    document = await get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
    return document


@router.post(
    "/workflows/{workflow_id}/steps/{step_id}/decision",
    response_model=WorkflowStateRead,
)
async def workflow_step_decision(
    workflow_id: UUID,
    step_id: UUID,
    payload: DecisionRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> WorkflowStateRead:
    return await decide_step(session, workflow_id, step_id, user, payload, request)


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
) -> DashboardSummary:
    visibility = document_visibility_filter(user)
    base = select(Document.id)
    if visibility is not None:
        base = base.where(visibility)
    visible_subquery = base.subquery()

    total_result = await session.execute(
        select(func.count()).select_from(visible_subquery)
    )
    awaiting_query = select(func.count(Workflow.id)).where(
        Workflow.status == "awaiting_review"
    )
    if visibility is not None:
        awaiting_query = awaiting_query.join(
            Document, Workflow.document_id == Document.id
        ).where(visibility)
    awaiting_result = await session.execute(awaiting_query)
    failures_query = select(func.count(Document.id)).where(
        Document.status == "extraction_failed"
    )
    if visibility is not None:
        failures_query = failures_query.where(visibility)
    failures_result = await session.execute(failures_query)
    latest_runs = (
        select(
            ExtractionRun.document_id,
            func.max(ExtractionRun.created_at).label("created_at"),
        )
        .group_by(ExtractionRun.document_id)
        .subquery()
    )
    missing_query = (
        select(func.count(ExtractionRun.id))
        .join(
            latest_runs,
            and_(
                ExtractionRun.document_id == latest_runs.c.document_id,
                ExtractionRun.created_at == latest_runs.c.created_at,
            ),
        )
        .where(
            ExtractionRun.status == "completed",
            func.jsonb_array_length(ExtractionRun.missing_fields) > 0,
        )
    )
    if visibility is not None:
        missing_query = missing_query.join(
            Document, ExtractionRun.document_id == Document.id
        ).where(visibility)
    missing_fields_result = await session.execute(missing_query)
    grouped_query = (
        select(Document.workflow_type, func.count(Document.id))
        .group_by(Document.workflow_type)
        .order_by(Document.workflow_type)
    )
    if visibility is not None:
        grouped_query = grouped_query.where(visibility)
    grouped_result = await session.execute(grouped_query)
    return DashboardSummary(
        total_documents=int(total_result.scalar_one()),
        awaiting_review=int(awaiting_result.scalar_one()),
        recent_failures=int(failures_result.scalar_one()),
        documents_with_missing_fields=int(missing_fields_result.scalar_one()),
        average_processing_seconds=None,
        documents_by_workflow=[
            QueueCount(workflow_type=row[0], count=int(row[1])) for row in grouped_result.all()
        ],
    )


@router.get("/audit-events", response_model=AuditEventListResponse)
async def audit_events(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: CurrentUserDep,
    document_id: UUID | None = None,
) -> AuditEventListResponse:
    statement = select(AuditEvent).order_by(AuditEvent.timestamp.desc())
    if document_id is not None:
        await _load_authorized_document(session, document_id, user)
        statement = statement.where(AuditEvent.document_id == document_id)
    elif not is_admin(user):
        visibility = document_visibility_filter(user)
        if visibility is None:
            pass
        else:
            visible_doc_ids = (
                select(Document.id).where(visibility).subquery()
            )
            statement = statement.where(
                AuditEvent.document_id.in_(select(visible_doc_ids.c.id))
            )
    result = await session.execute(statement)
    return AuditEventListResponse(
        audit_events=[AuditEventRead.model_validate(event) for event in result.scalars().all()]
    )
