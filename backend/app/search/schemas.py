from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IndexingRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    document_version_id: UUID
    status: str
    read_model_id: str
    embedding_model: str | None
    chunk_count: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chunk_index: int
    content: str
    page_number: int | None
    char_count: int


def _empty_chunks() -> list[DocumentChunkRead]:
    return []


class IndexingResponse(BaseModel):
    document_id: UUID
    status: str
    latest_run: IndexingRunRead | None
    chunk_count: int
    chunks: list[DocumentChunkRead] = Field(default_factory=_empty_chunks)


class CitationRead(BaseModel):
    chunk_id: str
    page_number: int | None = None
    content: str
    score: float | None = None


class QuestionAnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    question: str
    answer: str | None
    status: str
    citations: list[CitationRead]
    model_id: str | None
    error_message: str | None
    created_at: datetime


class QuestionListResponse(BaseModel):
    questions: list[QuestionAnswerRead]


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
