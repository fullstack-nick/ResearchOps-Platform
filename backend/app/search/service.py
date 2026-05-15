from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.database.models import (
    AuditEvent,
    Document,
    DocumentChunk,
    DocumentQuestion,
    IndexingRun,
    User,
)
from app.documents.azure_storage import download_document_blob
from app.search.azure_client import (
    analyze_document_text,
    delete_chunks_from_index,
    embed_texts,
    ensure_search_index,
    generate_grounded_answer,
    search_document_chunks,
    upload_chunk_documents,
)
from app.search.chunking import ChunkText, chunk_pages, normalize_read_result
from app.search.schemas import DocumentChunkRead, IndexingResponse, IndexingRunRead


def indexing_run_query() -> Select[tuple[IndexingRun]]:
    return select(IndexingRun).options(
        selectinload(IndexingRun.chunks),
        selectinload(IndexingRun.document).selectinload(Document.workflow),
        selectinload(IndexingRun.document_version),
    )


async def get_latest_indexing_run(
    session: AsyncSession, document_id: uuid.UUID
) -> IndexingRun | None:
    result = await session.execute(
        indexing_run_query()
        .where(IndexingRun.document_id == document_id)
        .order_by(IndexingRun.created_at.desc(), IndexingRun.id.desc())
        .limit(1)
    )
    return result.scalars().unique().one_or_none()


async def get_document_indexing(
    session: AsyncSession, document_id: uuid.UUID
) -> IndexingResponse:
    document_result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    if document_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    latest_run = await get_latest_indexing_run(session, document_id)
    if latest_run is None:
        return IndexingResponse(
            document_id=document_id,
            status="not_requested",
            latest_run=None,
            chunk_count=0,
            chunks=[],
        )
    return IndexingResponse(
        document_id=document_id,
        status=latest_run.status,
        latest_run=IndexingRunRead.model_validate(latest_run),
        chunk_count=latest_run.chunk_count,
        chunks=[DocumentChunkRead.model_validate(chunk) for chunk in latest_run.chunks],
    )


async def retry_indexing(
    session: AsyncSession, document_id: uuid.UUID, request: Request, user: User
) -> IndexingResponse:
    document_result = await session.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.versions), selectinload(Document.workflow))
    )
    document = document_result.scalars().unique().one_or_none()
    if document is None or not document.versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    latest_run = await get_latest_indexing_run(session, document_id)
    if latest_run is not None and latest_run.status in {"pending", "processing"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Indexing is already pending or running for this document.",
        )

    settings = get_settings()
    run_id = uuid.uuid4()
    latest_version = document.versions[-1]
    run = IndexingRun(
        id=run_id,
        document_id=document.id,
        document_version_id=latest_version.id,
        status="pending",
        read_model_id=settings.azure_document_intelligence_read_model_id,
        embedding_model=settings.azure_openai_embedding_deployment,
        chunk_count=0,
    )
    session.add(run)
    session.add(
        AuditEvent(
            actor_type="user",
            actor_id=user.id,
            document_id=document.id,
            workflow_id=document.workflow.id if document.workflow else None,
            event_type="indexing.requested",
            after_value={"indexing_run_id": str(run_id), "status": "pending"},
            reason="Manual document indexing retry requested",
            source_ip=request.client.host if request.client else None,
            correlation_id=request.state.correlation_id,
        )
    )
    await session.commit()
    return await get_document_indexing(session, document_id)


async def process_next_pending_indexing_run(session: AsyncSession) -> bool:
    run_id = await claim_next_pending_indexing_run(session)
    if run_id is None:
        return False
    try:
        await complete_indexing_run(session, run_id)
    except Exception as exc:
        await session.rollback()
        await mark_indexing_failed(session, run_id, str(exc))
    return True


async def claim_next_pending_indexing_run(
    session: AsyncSession,
) -> uuid.UUID | None:
    result = await session.execute(
        select(IndexingRun)
        .where(IndexingRun.status == "pending")
        .order_by(IndexingRun.created_at, IndexingRun.id)
        .with_for_update(skip_locked=True)
        .limit(1)
        .options(selectinload(IndexingRun.document).selectinload(Document.workflow))
    )
    run = result.scalars().unique().one_or_none()
    if run is None:
        return None
    run.status = "processing"
    run.started_at = datetime.now(UTC)
    session.add(
        AuditEvent(
            actor_type="system",
            actor_id=None,
            document_id=run.document_id,
            workflow_id=run.document.workflow.id if run.document.workflow else None,
            event_type="indexing.started",
            after_value={"indexing_run_id": str(run.id), "status": "processing"},
            reason="Indexer claimed indexing run",
            source_ip=None,
            correlation_id=str(uuid.uuid4()),
        )
    )
    await session.commit()
    return run.id


async def complete_indexing_run(session: AsyncSession, run_id: uuid.UUID) -> None:
    run = await _get_indexing_run(session, run_id)
    version = run.document_version
    if version.storage_provider != "azure_blob":
        raise RuntimeError("Indexing requires an Azure Blob backed document version.")
    if not version.storage_container or not version.storage_object_key:
        raise RuntimeError("Document version is missing Azure Blob metadata.")

    settings = get_settings()
    document_bytes = download_document_blob(
        settings, version.storage_container, version.storage_object_key
    )
    read_result = analyze_document_text(settings, document_bytes)
    pages = normalize_read_result(read_result)
    chunks = chunk_pages(
        pages, settings.indexing_chunk_size, settings.indexing_chunk_overlap
    )
    if not chunks:
        raise RuntimeError("No readable text content was found for indexing.")

    embeddings = embed_texts(settings, [chunk.content for chunk in chunks])
    if len(embeddings) != len(chunks):
        raise RuntimeError("Embedding count did not match chunk count.")

    ensure_search_index(settings)
    delete_chunks_from_index(settings, str(run.document_id))
    search_documents: list[dict[str, Any]] = [
        {
            "chunk_id": f"{run.document_id}_{chunk.chunk_index}",
            "document_id": str(run.document_id),
            "document_version_id": str(run.document_version_id),
            "workflow_type": run.document.workflow_type,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "content": chunk.content,
            "content_vector": embedding,
        }
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    upload_chunk_documents(settings, search_documents)
    await _persist_indexing_chunks(session, run, chunks)


async def _persist_indexing_chunks(
    session: AsyncSession, run: IndexingRun, chunks: list[ChunkText]
) -> None:
    await session.execute(
        delete(DocumentChunk).where(DocumentChunk.indexing_run_id == run.id)
    )
    for chunk in chunks:
        session.add(
            DocumentChunk(
                document_id=run.document_id,
                document_version_id=run.document_version_id,
                indexing_run_id=run.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                char_count=chunk.char_count,
                search_document_key=f"{run.document_id}_{chunk.chunk_index}",
            )
        )
    run.status = "completed"
    run.chunk_count = len(chunks)
    run.error_message = None
    run.completed_at = datetime.now(UTC)
    session.add(
        AuditEvent(
            actor_type="system",
            actor_id=None,
            document_id=run.document_id,
            workflow_id=run.document.workflow.id if run.document.workflow else None,
            event_type="indexing.completed",
            after_value={
                "indexing_run_id": str(run.id),
                "chunk_count": len(chunks),
            },
            reason="Azure AI Search indexing completed",
            source_ip=None,
            correlation_id=str(uuid.uuid4()),
        )
    )
    await session.commit()


async def mark_indexing_failed(
    session: AsyncSession, run_id: uuid.UUID, error_message: str
) -> None:
    run = await _get_indexing_run(session, run_id)
    run.status = "failed"
    run.error_message = error_message[:2000]
    run.completed_at = datetime.now(UTC)
    session.add(
        AuditEvent(
            actor_type="system",
            actor_id=None,
            document_id=run.document_id,
            workflow_id=run.document.workflow.id if run.document.workflow else None,
            event_type="indexing.failed",
            after_value={
                "indexing_run_id": str(run.id),
                "error_message": run.error_message,
            },
            reason="Azure AI Search indexing failed",
            source_ip=None,
            correlation_id=str(uuid.uuid4()),
        )
    )
    await session.commit()


async def _get_indexing_run(session: AsyncSession, run_id: uuid.UUID) -> IndexingRun:
    result = await session.execute(
        indexing_run_query().where(IndexingRun.id == run_id)
    )
    run = result.scalars().unique().one_or_none()
    if run is None:
        raise RuntimeError(f"Indexing run {run_id} was not found.")
    return run


async def answer_document_question(
    session: AsyncSession,
    document_id: uuid.UUID,
    question: str,
    request: Request,
    user: User,
) -> DocumentQuestion:
    document_result = await session.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.workflow))
    )
    document = document_result.scalars().unique().one_or_none()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )

    latest_run = await get_latest_indexing_run(session, document_id)
    if latest_run is None or latest_run.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This document is not indexed for Q&A yet.",
        )

    settings = get_settings()
    cleaned_question = question.strip()
    citations: list[dict[str, Any]] = []
    answer: str | None = None
    question_status = "completed"
    error_message: str | None = None
    try:
        query_vector = (
            await asyncio.to_thread(embed_texts, settings, [cleaned_question])
        )[0]
        retrieved = await asyncio.to_thread(
            search_document_chunks,
            settings,
            str(document_id),
            cleaned_question,
            query_vector,
            settings.qa_top_chunks,
        )
        if not retrieved:
            answer = (
                "I could not find anything relevant to that question in this document."
            )
        else:
            answer = await asyncio.to_thread(
                generate_grounded_answer, settings, cleaned_question, retrieved
            )
            citations = [
                {
                    "chunk_id": str(chunk["chunk_id"]),
                    "page_number": chunk.get("page_number"),
                    "content": str(chunk["content"])[:600],
                    "score": chunk.get("score"),
                }
                for chunk in retrieved
            ]
    except HTTPException:
        raise
    except Exception as exc:
        question_status = "failed"
        error_message = str(exc)[:2000]
        answer = None

    question_id = uuid.uuid4()
    record = DocumentQuestion(
        id=question_id,
        document_id=document_id,
        question=cleaned_question,
        answer=answer,
        status=question_status,
        citations=citations,
        model_id=settings.azure_openai_chat_deployment,
        error_message=error_message,
        asked_by_user_id=user.id,
    )
    session.add(record)
    session.add(
        AuditEvent(
            actor_type="user",
            actor_id=user.id,
            document_id=document_id,
            workflow_id=document.workflow.id if document.workflow else None,
            event_type=(
                "document.question_asked"
                if question_status == "completed"
                else "document.question_failed"
            ),
            after_value={
                "question_id": str(question_id),
                "status": question_status,
                "citation_count": len(citations),
            },
            reason=cleaned_question[:480],
            source_ip=request.client.host if request.client else None,
            correlation_id=request.state.correlation_id,
        )
    )
    await session.commit()
    await session.refresh(record)
    return record


async def list_document_questions(
    session: AsyncSession, document_id: uuid.UUID
) -> list[DocumentQuestion]:
    document_result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    if document_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    result = await session.execute(
        select(DocumentQuestion)
        .where(DocumentQuestion.document_id == document_id)
        .order_by(DocumentQuestion.created_at.desc(), DocumentQuestion.id.desc())
    )
    return list(result.scalars().all())
