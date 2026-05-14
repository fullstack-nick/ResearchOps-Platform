from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.schemas import AuditEventListResponse, AuditEventRead
from app.dashboard.schemas import DashboardSummary, QueueCount
from app.database.models import AuditEvent, Document, Workflow
from app.database.session import get_session
from app.documents.schemas import DocumentListResponse, DocumentRead, UploadResponse
from app.documents.service import (
    create_document_upload,
    get_document,
    get_document_file_path,
    list_documents,
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
) -> FileResponse:
    document, path = await get_document_file_path(session, document_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=document.safe_filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=60"},
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
        select(func.count(Workflow.id)).where(Workflow.status == "failed")
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
