from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.database.models import WORKFLOW_TYPES
from app.extraction.schemas import ExtractionSummaryRead


class WorkflowStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_name: str
    status: str
    assigned_role: str
    step_order: int
    completed_at: datetime | None
    created_at: datetime


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_type: str
    status: str
    current_step: str
    created_at: datetime
    updated_at: datetime
    steps: list[WorkflowStepRead] = Field(default_factory=lambda: list[WorkflowStepRead]())


class DocumentVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    storage_provider: str
    storage_container: str | None
    storage_object_key: str | None
    size_bytes: int
    sha256: str
    created_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_user_id: UUID
    original_filename: str
    safe_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    workflow_type: str
    status: str
    research_group: str | None = None
    created_at: datetime
    updated_at: datetime
    workflow: WorkflowRead
    extraction_summary: ExtractionSummaryRead
    versions: list[DocumentVersionRead] = Field(
        default_factory=lambda: list[DocumentVersionRead]()
    )


class DocumentListResponse(BaseModel):
    documents: list[DocumentRead]


class UploadResponse(BaseModel):
    document: DocumentRead


class WorkflowTypeList(BaseModel):
    values: tuple[str, ...] = WORKFLOW_TYPES
