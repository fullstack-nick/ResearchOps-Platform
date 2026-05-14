from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.schemas import AuditEventListResponse, AuditEventRead
from app.dashboard.schemas import DashboardSummary, QueueCount
from app.database.models import AuditEvent, Document, ExtractionRun, Workflow
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

router = APIRouter()


@router.post("/documents", response_model=UploadResponse, status_code=201)
async def upload_document(
    request: Request,
    workflow_type: Annotated[str, Query()],
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UploadResponse:
    document = await create_document_upload(session, file, workflow_type, request)
    return UploadResponse(document=DocumentRead.model_validate(document))


@router.get("/documents", response_model=DocumentListResponse)
async def documents(
    session: Annotated[AsyncSession, Depends(get_session)],
    workflow_type: str | None = None,
    status: str | None = None,
) -> DocumentListResponse:
    rows = await list_documents(session, workflow_type=workflow_type, status_filter=status)
    return DocumentListResponse(documents=[DocumentRead.model_validate(row) for row in rows])


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def document_detail(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentRead:
    document = await get_document(session, document_id)
    if document is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return DocumentRead.model_validate(document)


@router.get("/documents/{document_id}/file")
async def document_file(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
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
) -> ExtractionResponse:
    return await get_document_extraction(session, document_id)


@router.post("/documents/{document_id}/extraction/retry", response_model=ExtractionResponse)
async def retry_document_extraction(
    document_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExtractionResponse:
    return await retry_extraction(session, document_id, request)


@router.patch("/documents/{document_id}/fields/{field_id}", response_model=ExtractedFieldRead)
async def correct_document_field(
    document_id: UUID,
    field_id: UUID,
    payload: FieldCorrectionRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExtractedFieldRead:
    return await correct_extracted_field(session, document_id, field_id, payload, request)


@router.get("/documents/{document_id}/indexing", response_model=IndexingResponse)
async def document_indexing(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IndexingResponse:
    return await get_document_indexing(session, document_id)


@router.post("/documents/{document_id}/indexing/retry", response_model=IndexingResponse)
async def retry_document_indexing(
    document_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IndexingResponse:
    return await retry_indexing(session, document_id, request)


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
) -> QuestionAnswerRead:
    record = await answer_document_question(session, document_id, payload.question, request)
    return QuestionAnswerRead.model_validate(record)


@router.get("/documents/{document_id}/questions", response_model=QuestionListResponse)
async def document_questions(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> QuestionListResponse:
    records = await list_document_questions(session, document_id)
    return QuestionListResponse(
        questions=[QuestionAnswerRead.model_validate(record) for record in records]
    )


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DashboardSummary:
    total_result = await session.execute(select(func.count(Document.id)))
    awaiting_result = await session.execute(
        select(func.count(Workflow.id)).where(Workflow.status == "awaiting_review")
    )
    failures_result = await session.execute(
        select(func.count(Document.id)).where(Document.status == "extraction_failed")
    )
    latest_runs = (
        select(
            ExtractionRun.document_id,
            func.max(ExtractionRun.created_at).label("created_at"),
        )
        .group_by(ExtractionRun.document_id)
        .subquery()
    )
    missing_fields_result = await session.execute(
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
    grouped_result = await session.execute(
        select(Document.workflow_type, func.count(Document.id))
        .group_by(Document.workflow_type)
        .order_by(Document.workflow_type)
    )
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
    document_id: UUID | None = None,
) -> AuditEventListResponse:
    statement = select(AuditEvent).order_by(AuditEvent.timestamp.desc())
    if document_id is not None:
        statement = statement.where(AuditEvent.document_id == document_id)
    result = await session.execute(statement)
    return AuditEventListResponse(
        audit_events=[AuditEventRead.model_validate(event) for event in result.scalars().all()]
    )
