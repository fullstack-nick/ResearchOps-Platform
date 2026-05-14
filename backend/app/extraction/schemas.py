from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExtractionSummaryRead(BaseModel):
    status: str
    missing_field_count: int
    latest_run_id: UUID | None
    failed: bool


class ExtractionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    document_version_id: UUID
    status: str
    model_id: str
    missing_fields: list[str]
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ExtractedFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    field_key: str
    label: str
    value: str | None
    display_value: str | None
    value_type: str
    confidence: float | None
    source_page: int | None
    source_regions: list[dict[str, Any]]
    raw_value: dict[str, Any] | None
    is_missing: bool
    display_order: int
    corrected_value: str | None
    correction_reason: str | None
    corrected_at: datetime | None


class ExtractedLineItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_index: int
    description: str | None
    quantity: float | None
    unit_price: float | None
    amount: float | None
    currency: str | None
    confidence: float | None
    source_page: int | None
    source_regions: list[dict[str, Any]]
    raw_value: dict[str, Any] | None


def _empty_fields() -> list[ExtractedFieldRead]:
    return []


def _empty_line_items() -> list[ExtractedLineItemRead]:
    return []


def _empty_missing_fields() -> list[str]:
    return []


class ExtractionResponse(BaseModel):
    document_id: UUID
    available: bool
    status: str
    latest_run: ExtractionRunRead | None
    fields: list[ExtractedFieldRead] = Field(default_factory=_empty_fields)
    missing_fields: list[str] = Field(default_factory=_empty_missing_fields)
    line_items: list[ExtractedLineItemRead] = Field(default_factory=_empty_line_items)


class FieldCorrectionRequest(BaseModel):
    corrected_value: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=3, max_length=2000)
