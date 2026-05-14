import uuid

from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.database.models import (
    DEMO_USER_ID,
    WORKFLOW_TYPES,
    AuditEvent,
    Document,
    DocumentVersion,
    Workflow,
    WorkflowStep,
)
from app.documents.storage import (
    read_limited_upload,
    resolve_storage_path,
    validate_pdf_upload,
    write_document_bytes,
)


def validate_workflow_type(workflow_type: str) -> None:
    if workflow_type not in WORKFLOW_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"workflow_type must be one of: {', '.join(WORKFLOW_TYPES)}",
        )


def document_query() -> Select[tuple[Document]]:
    return select(Document).options(
        selectinload(Document.workflow).selectinload(Workflow.steps),
        selectinload(Document.versions),
    )


async def create_document_upload(
    session: AsyncSession,
    upload: UploadFile,
    workflow_type: str,
    request: Request,
) -> Document:
    validate_workflow_type(workflow_type)
    safe_filename = validate_pdf_upload(upload)
    settings = get_settings()
    content, digest = await read_limited_upload(upload, settings.max_upload_bytes)

    document_id = uuid.uuid4()
    version_id = uuid.uuid4()
    workflow_id = uuid.uuid4()
    relative_storage_path = write_document_bytes(
        settings=settings,
        document_id=document_id,
        version_id=version_id,
        safe_filename=safe_filename,
        content=content,
    )

    source_ip = request.client.host if request.client else None
    correlation_id = request.state.correlation_id
    document = Document(
        id=document_id,
        owner_user_id=DEMO_USER_ID,
        original_filename=upload.filename or safe_filename,
        safe_filename=safe_filename,
        content_type="application/pdf",
        size_bytes=len(content),
        sha256=digest,
        workflow_type=workflow_type,
        status="uploaded",
    )
    version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        version_number=1,
        storage_path=relative_storage_path,
        size_bytes=len(content),
        sha256=digest,
        created_by_user_id=DEMO_USER_ID,
    )
    workflow = Workflow(
        id=workflow_id,
        document_id=document_id,
        workflow_type=workflow_type,
        status="awaiting_review",
        current_step="intake_review",
    )
    step = WorkflowStep(
        workflow_id=workflow_id,
        step_name="intake_review",
        status="pending",
        assigned_role="operations_admin",
    )
    document_uploaded = AuditEvent(
        actor_type="user",
        actor_id=DEMO_USER_ID,
        document_id=document_id,
        workflow_id=workflow_id,
        event_type="document.uploaded",
        after_value={
            "filename": document.original_filename,
            "workflow_type": workflow_type,
            "size_bytes": len(content),
            "sha256": digest,
        },
        reason="Phase 1 local document intake",
        source_ip=source_ip,
        correlation_id=correlation_id,
    )
    workflow_created = AuditEvent(
        actor_type="system",
        actor_id=None,
        document_id=document_id,
        workflow_id=workflow_id,
        event_type="workflow.created",
        after_value={
            "status": "awaiting_review",
            "current_step": "intake_review",
            "assigned_role": "operations_admin",
        },
        reason="Workflow created from document upload",
        source_ip=source_ip,
        correlation_id=correlation_id,
    )

    session.add_all([document, version, workflow, step, document_uploaded, workflow_created])
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        stored = resolve_storage_path(settings, relative_storage_path)
        if stored.exists():
            stored.unlink()
        raise

    loaded = await get_document(session, document_id)
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed.",
        )
    return loaded


async def list_documents(
    session: AsyncSession,
    workflow_type: str | None = None,
    status_filter: str | None = None,
) -> list[Document]:
    statement = document_query().order_by(Document.created_at.desc())
    if workflow_type is not None:
        validate_workflow_type(workflow_type)
        statement = statement.where(Document.workflow_type == workflow_type)
    if status_filter is not None:
        statement = statement.where(Document.status == status_filter)
    result = await session.execute(statement)
    return list(result.scalars().unique().all())


async def get_document(session: AsyncSession, document_id: uuid.UUID) -> Document | None:
    result = await session.execute(document_query().where(Document.id == document_id))
    return result.scalars().unique().one_or_none()


async def get_document_file_path(session: AsyncSession, document_id: uuid.UUID):
    document = await get_document(session, document_id)
    if document is None or not document.versions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    latest = document.versions[-1]
    path = resolve_storage_path(get_settings(), latest.storage_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found.")
    return document, path


async def count_documents(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Document.id)))
    return int(result.scalar_one())
