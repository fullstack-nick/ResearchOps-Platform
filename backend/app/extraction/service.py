from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.database.models import (
    DEMO_USER_ID,
    AuditEvent,
    Document,
    ExtractedField,
    ExtractedLineItem,
    ExtractionRun,
)
from app.documents.azure_storage import download_document_blob
from app.extraction.azure_client import analyze_invoice_document
from app.extraction.normalizer import NormalizedInvoice, normalize_invoice_result
from app.extraction.schemas import (
    ExtractedFieldRead,
    ExtractedLineItemRead,
    ExtractionResponse,
    ExtractionRunRead,
    FieldCorrectionRequest,
)

AnalyzeInvoice = Callable[[Settings, bytes], Any]
DownloadBlob = Callable[[Settings, str, str], bytes]


def extraction_run_query() -> Select[tuple[ExtractionRun]]:
    return select(ExtractionRun).options(
        selectinload(ExtractionRun.fields),
        selectinload(ExtractionRun.line_items),
        selectinload(ExtractionRun.document).selectinload(Document.workflow),
        selectinload(ExtractionRun.document_version),
    )


async def get_document_extraction(
    session: AsyncSession, document_id: uuid.UUID
) -> ExtractionResponse:
    document_result = await session.execute(select(Document).where(Document.id == document_id))
    document = document_result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if document.workflow_type != "procurement":
        return ExtractionResponse(
            document_id=document_id,
            available=False,
            status="unavailable",
            latest_run=None,
            fields=[],
            missing_fields=[],
            line_items=[],
        )

    latest_run = await get_latest_extraction_run(session, document_id)
    if latest_run is None:
        return ExtractionResponse(
            document_id=document_id,
            available=True,
            status="not_requested",
            latest_run=None,
            fields=[],
            missing_fields=[],
            line_items=[],
        )
    return _response_from_run(latest_run)


async def get_latest_extraction_run(
    session: AsyncSession, document_id: uuid.UUID
) -> ExtractionRun | None:
    result = await session.execute(
        extraction_run_query()
        .where(ExtractionRun.document_id == document_id)
        .order_by(ExtractionRun.created_at.desc(), ExtractionRun.id.desc())
        .limit(1)
    )
    return result.scalars().unique().one_or_none()


async def retry_extraction(
    session: AsyncSession, document_id: uuid.UUID, request: Request
) -> ExtractionResponse:
    document_result = await session.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.versions),
            selectinload(Document.workflow),
            selectinload(Document.extraction_runs),
        )
    )
    document = document_result.scalars().unique().one_or_none()
    if document is None or not document.versions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if document.workflow_type != "procurement":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phase 2 extraction is only available for procurement invoices.",
        )
    latest_run = document.extraction_runs[-1] if document.extraction_runs else None
    if latest_run is not None and latest_run.status in {"pending", "processing"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Extraction is already pending or running for this document.",
        )

    run_id = uuid.uuid4()
    latest_version = document.versions[-1]
    run = ExtractionRun(
        id=run_id,
        document_id=document.id,
        document_version_id=latest_version.id,
        status="pending",
        model_id=get_settings().azure_document_intelligence_model_id,
        missing_fields=[],
    )
    document.status = "extraction_pending"
    session.add(run)
    session.add(
        AuditEvent(
            actor_type="system",
            actor_id=None,
            document_id=document.id,
            workflow_id=document.workflow.id if document.workflow else None,
            event_type="extraction.requested",
            after_value={"extraction_run_id": str(run_id), "status": "pending"},
            reason="Manual extraction retry requested",
            source_ip=request.client.host if request.client else None,
            correlation_id=request.state.correlation_id,
        )
    )
    await session.commit()
    latest = await get_latest_extraction_run(session, document_id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Extraction retry was not created.",
        )
    return _response_from_run(latest)


async def correct_extracted_field(
    session: AsyncSession,
    document_id: uuid.UUID,
    field_id: uuid.UUID,
    payload: FieldCorrectionRequest,
    request: Request,
) -> ExtractedFieldRead:
    result = await session.execute(
        select(ExtractedField)
        .where(ExtractedField.document_id == document_id, ExtractedField.id == field_id)
        .options(
            selectinload(ExtractedField.extraction_run)
            .selectinload(ExtractionRun.document)
            .selectinload(Document.workflow)
        )
    )
    field = result.scalars().unique().one_or_none()
    if field is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracted field not found.",
        )

    before = {
        "field_key": field.field_key,
        "value": field.value,
        "corrected_value": field.corrected_value,
        "is_missing": field.is_missing,
    }
    corrected_value = payload.corrected_value.strip()
    field.corrected_value = corrected_value
    field.correction_reason = payload.reason.strip()
    field.corrected_by_user_id = DEMO_USER_ID
    field.corrected_at = datetime.now(UTC)
    field.is_missing = False
    await _refresh_run_missing_fields(session, field.extraction_run)
    session.add(
        AuditEvent(
            actor_type="user",
            actor_id=DEMO_USER_ID,
            document_id=document_id,
            workflow_id=field.extraction_run.document.workflow.id
            if field.extraction_run.document.workflow
            else None,
            event_type="field.corrected",
            before_value=before,
            after_value={
                "field_key": field.field_key,
                "corrected_value": corrected_value,
                "is_missing": field.is_missing,
            },
            reason=payload.reason.strip(),
            source_ip=request.client.host if request.client else None,
            correlation_id=request.state.correlation_id,
        )
    )
    await session.commit()
    await session.refresh(field)
    return ExtractedFieldRead.model_validate(field)


async def process_next_pending_run(
    session: AsyncSession,
    analyze: AnalyzeInvoice = analyze_invoice_document,
    download_blob: DownloadBlob = download_document_blob,
) -> bool:
    run_id = await claim_next_pending_run(session)
    if run_id is None:
        return False
    try:
        await complete_extraction_run(session, run_id, analyze=analyze, download_blob=download_blob)
    except Exception as exc:
        await session.rollback()
        await mark_extraction_failed(session, run_id, str(exc))
    return True


async def claim_next_pending_run(session: AsyncSession) -> uuid.UUID | None:
    result = await session.execute(
        select(ExtractionRun)
        .where(ExtractionRun.status == "pending")
        .order_by(ExtractionRun.created_at, ExtractionRun.id)
        .with_for_update(skip_locked=True)
        .limit(1)
        .options(
            selectinload(ExtractionRun.document).selectinload(Document.workflow),
        )
    )
    run = result.scalars().unique().one_or_none()
    if run is None:
        return None
    run.status = "processing"
    run.started_at = datetime.now(UTC)
    run.document.status = "extracting"
    session.add(
        AuditEvent(
            actor_type="system",
            actor_id=None,
            document_id=run.document_id,
            workflow_id=run.document.workflow.id if run.document.workflow else None,
            event_type="extraction.started",
            after_value={"extraction_run_id": str(run.id), "status": "processing"},
            reason="Worker claimed extraction run",
            source_ip=None,
            correlation_id=str(uuid.uuid4()),
        )
    )
    await session.commit()
    return run.id


async def complete_extraction_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    analyze: AnalyzeInvoice = analyze_invoice_document,
    download_blob: DownloadBlob = download_document_blob,
) -> None:
    run = await _get_run_for_processing(session, run_id)
    version = run.document_version
    if version.storage_provider != "azure_blob":
        raise RuntimeError("Extraction requires an Azure Blob backed document version.")
    if not version.storage_container or not version.storage_object_key:
        raise RuntimeError("Document version is missing Azure Blob metadata.")

    settings = get_settings()
    document_bytes = download_blob(settings, version.storage_container, version.storage_object_key)
    azure_result = analyze(settings, document_bytes)
    invoice = normalize_invoice_result(azure_result)
    await persist_invoice_extraction(session, run, invoice)


async def persist_invoice_extraction(
    session: AsyncSession, run: ExtractionRun, invoice: NormalizedInvoice
) -> None:
    await session.execute(delete(ExtractedField).where(ExtractedField.extraction_run_id == run.id))
    await session.execute(
        delete(ExtractedLineItem).where(ExtractedLineItem.extraction_run_id == run.id)
    )

    for field in invoice.fields:
        session.add(
            ExtractedField(
                document_id=run.document_id,
                extraction_run_id=run.id,
                field_key=field.field_key,
                label=field.label,
                value=field.value,
                value_type=field.value_type,
                confidence=field.confidence,
                source_page=field.source_page,
                source_regions=field.source_regions,
                raw_value=field.raw_value,
                is_missing=field.is_missing,
                display_order=field.display_order,
            )
        )
    for item in invoice.line_items:
        session.add(
            ExtractedLineItem(
                document_id=run.document_id,
                extraction_run_id=run.id,
                item_index=item.item_index,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                amount=item.amount,
                currency=item.currency,
                confidence=item.confidence,
                source_page=item.source_page,
                source_regions=item.source_regions,
                raw_value=item.raw_value,
            )
        )

    run.status = "completed"
    run.model_id = invoice.model_id or run.model_id
    run.missing_fields = invoice.missing_fields
    run.error_message = None
    run.completed_at = datetime.now(UTC)
    run.document.status = "extracted"
    session.add(
        AuditEvent(
            actor_type="system",
            actor_id=None,
            document_id=run.document_id,
            workflow_id=run.document.workflow.id if run.document.workflow else None,
            event_type="extraction.completed",
            after_value={
                "extraction_run_id": str(run.id),
                "field_count": len(invoice.fields),
                "line_item_count": len(invoice.line_items),
                "missing_fields": invoice.missing_fields,
            },
            reason="Azure Document Intelligence extraction completed",
            source_ip=None,
            correlation_id=str(uuid.uuid4()),
        )
    )
    await session.commit()


async def mark_extraction_failed(
    session: AsyncSession, run_id: uuid.UUID, error_message: str
) -> None:
    run = await _get_run_for_processing(session, run_id)
    run.status = "failed"
    run.error_message = error_message[:2000]
    run.completed_at = datetime.now(UTC)
    run.document.status = "extraction_failed"
    session.add(
        AuditEvent(
            actor_type="system",
            actor_id=None,
            document_id=run.document_id,
            workflow_id=run.document.workflow.id if run.document.workflow else None,
            event_type="extraction.failed",
            after_value={"extraction_run_id": str(run.id), "error_message": run.error_message},
            reason="Azure Document Intelligence extraction failed",
            source_ip=None,
            correlation_id=str(uuid.uuid4()),
        )
    )
    await session.commit()


async def _get_run_for_processing(session: AsyncSession, run_id: uuid.UUID) -> ExtractionRun:
    result = await session.execute(extraction_run_query().where(ExtractionRun.id == run_id))
    run = result.scalars().unique().one_or_none()
    if run is None:
        raise RuntimeError(f"Extraction run {run_id} was not found.")
    return run


async def _refresh_run_missing_fields(session: AsyncSession, run: ExtractionRun) -> None:
    fields_result = await session.execute(
        select(ExtractedField)
        .where(ExtractedField.extraction_run_id == run.id)
        .order_by(ExtractedField.display_order)
    )
    missing = [
        field.field_key
        for field in fields_result.scalars().all()
        if field.is_missing and not field.corrected_value
    ]
    line_count = await session.scalar(
        select(func.count(ExtractedLineItem.id)).where(
            ExtractedLineItem.extraction_run_id == run.id
        )
    )
    if int(line_count or 0) == 0:
        missing.append("line_items")
    run.missing_fields = missing


def _response_from_run(run: ExtractionRun) -> ExtractionResponse:
    return ExtractionResponse(
        document_id=run.document_id,
        available=True,
        status=run.status,
        latest_run=ExtractionRunRead.model_validate(run),
        fields=[ExtractedFieldRead.model_validate(field) for field in run.fields],
        missing_fields=run.missing_fields or [],
        line_items=[ExtractedLineItemRead.model_validate(item) for item in run.line_items],
    )
