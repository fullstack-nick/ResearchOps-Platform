import uuid
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.access import document_visibility_filter
from app.core.config import get_settings
from app.core.observability import record_counter, record_event, record_histogram
from app.database.models import (
    WORKFLOW_TYPES,
    AuditEvent,
    Document,
    DocumentVersion,
    ExtractionRun,
    IndexingRun,
    User,
    Workflow,
)
from app.documents.azure_storage import download_document_blob, upload_document_blob
from app.documents.storage import (
    read_limited_upload,
    resolve_storage_path,
    validate_pdf_upload,
)
from app.workflows.service import build_workflow_steps_for_type


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
        selectinload(Document.extraction_runs),
    )


async def create_document_upload(
    session: AsyncSession,
    upload: UploadFile,
    workflow_type: str,
    request: Request,
    user: User,
) -> Document:
    validate_workflow_type(workflow_type)
    safe_filename = validate_pdf_upload(upload)
    settings = get_settings()
    content, digest = await read_limited_upload(upload, settings.max_upload_bytes)

    document_id = uuid.uuid4()
    version_id = uuid.uuid4()
    workflow_id = uuid.uuid4()

    object_key = f"documents/{document_id}/versions/{version_id}/{safe_filename}"
    blob = upload_document_blob(
        settings=settings,
        object_key=object_key,
        content=content,
        content_type="application/pdf",
        metadata={
            "document_id": str(document_id),
            "version_id": str(version_id),
            "workflow_type": workflow_type,
            "sha256": digest,
        },
    )
    record_histogram(
        "researchops.documents.upload_size_bytes",
        len(content),
        {"workflow.type": workflow_type},
    )

    source_ip = request.client.host if request.client else None
    correlation_id = request.state.correlation_id
    extraction_requested = workflow_type == "procurement"
    document = Document(
        id=document_id,
        owner_user_id=user.id,
        original_filename=upload.filename or safe_filename,
        safe_filename=safe_filename,
        content_type="application/pdf",
        size_bytes=len(content),
        sha256=digest,
        workflow_type=workflow_type,
        status="extraction_pending" if extraction_requested else "uploaded",
        research_group=user.research_group,
    )
    version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        version_number=1,
        storage_path=blob.object_key,
        storage_provider="azure_blob",
        storage_container=blob.container,
        storage_object_key=blob.object_key,
        storage_url=blob.url,
        size_bytes=len(content),
        sha256=digest,
        created_by_user_id=user.id,
    )
    workflow_steps = build_workflow_steps_for_type(workflow_id, workflow_type)
    first_step = workflow_steps[0]
    workflow = Workflow(
        id=workflow_id,
        document_id=document_id,
        workflow_type=workflow_type,
        status="awaiting_review",
        current_step=first_step.step_name,
    )
    document_uploaded = AuditEvent(
        actor_type="user",
        actor_id=user.id,
        document_id=document_id,
        workflow_id=workflow_id,
        event_type="document.uploaded",
        after_value={
            "filename": document.original_filename,
            "workflow_type": workflow_type,
            "size_bytes": len(content),
            "sha256": digest,
            "research_group": user.research_group,
        },
        reason="Phase 2 Azure Blob document intake",
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
            "current_step": first_step.step_name,
            "step_names": [step.step_name for step in workflow_steps],
        },
        reason="Workflow created from document upload",
        source_ip=source_ip,
        correlation_id=correlation_id,
    )
    records: list[object] = [
        document,
        version,
        workflow,
        *workflow_steps,
        document_uploaded,
        workflow_created,
    ]

    if extraction_requested:
        extraction_run_id = uuid.uuid4()
        extraction_run = ExtractionRun(
            id=extraction_run_id,
            document_id=document_id,
            document_version_id=version_id,
            status="pending",
            model_id=settings.azure_document_intelligence_model_id,
            missing_fields=[],
        )
        extraction_audit = AuditEvent(
            actor_type="system",
            actor_id=None,
            document_id=document_id,
            workflow_id=workflow_id,
            event_type="extraction.requested",
            after_value={
                "extraction_run_id": str(extraction_run_id),
                "model_id": settings.azure_document_intelligence_model_id,
                "status": "pending",
            },
            reason="Automatic procurement invoice extraction queued",
            source_ip=source_ip,
            correlation_id=correlation_id,
        )
        records.extend([extraction_run, extraction_audit])

    indexing_run_id = uuid.uuid4()
    indexing_run = IndexingRun(
        id=indexing_run_id,
        document_id=document_id,
        document_version_id=version_id,
        status="pending",
        read_model_id=settings.azure_document_intelligence_read_model_id,
        embedding_model=settings.azure_openai_embedding_deployment,
        chunk_count=0,
    )
    indexing_audit = AuditEvent(
        actor_type="system",
        actor_id=None,
        document_id=document_id,
        workflow_id=workflow_id,
        event_type="indexing.requested",
        after_value={
            "indexing_run_id": str(indexing_run_id),
            "read_model_id": settings.azure_document_intelligence_read_model_id,
            "status": "pending",
        },
        reason="Automatic document indexing queued for Q&A",
        source_ip=source_ip,
        correlation_id=correlation_id,
    )
    records.extend([indexing_run, indexing_audit])

    session.add_all(records)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    loaded = await get_document(session, document_id)
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed.",
        )
    record_counter("researchops.documents.uploaded", 1, {"workflow.type": workflow_type})
    if extraction_requested:
        record_counter(
            "researchops.extraction.runs",
            1,
            {"workflow.type": workflow_type, "run.status": "pending"},
        )
    record_counter(
        "researchops.indexing.runs",
        1,
        {"workflow.type": workflow_type, "run.status": "pending"},
    )
    record_event(
        "document.uploaded",
        {"workflow.type": workflow_type, "document.id": str(document_id)},
    )
    return loaded


async def list_documents(
    session: AsyncSession,
    user: User,
    workflow_type: str | None = None,
    status_filter: str | None = None,
) -> list[Document]:
    statement = document_query().order_by(Document.created_at.desc())
    visibility = document_visibility_filter(user)
    if visibility is not None:
        statement = statement.where(visibility)
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


async def get_document_file_path(
    session: AsyncSession, document_id: uuid.UUID
) -> tuple[Document, Path]:
    document = await get_document(session, document_id)
    if document is None or not document.versions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    latest = document.versions[-1]
    path = resolve_storage_path(get_settings(), latest.storage_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found.")
    return document, path


async def get_document_file_bytes(
    session: AsyncSession, document_id: uuid.UUID
) -> tuple[Document, bytes]:
    document = await get_document(session, document_id)
    if document is None or not document.versions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    latest = document.versions[-1]
    if latest.storage_provider == "azure_blob":
        if not latest.storage_container or not latest.storage_object_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored Azure Blob metadata is incomplete.",
            )
        content = download_document_blob(
            get_settings(),
            container=latest.storage_container,
            object_key=latest.storage_object_key,
        )
        return document, content

    _, path = await get_document_file_path(session, document_id)
    return document, path.read_bytes()


async def count_documents(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Document.id)))
    return int(result.scalar_one())
