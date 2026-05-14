from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.database.models import WORKFLOW_TYPES


class WorkflowStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_name: str
    status: str
    assigned_role: str
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
    created_at: datetime
    updated_at: datetime
    workflow: WorkflowRead
    versions: list[DocumentVersionRead] = Field(
        default_factory=lambda: list[DocumentVersionRead]()
    )


class DocumentListResponse(BaseModel):
    documents: list[DocumentRead]


class UploadResponse(BaseModel):
    document: DocumentRead


class WorkflowTypeList(BaseModel):
    values: tuple[str, ...] = WORKFLOW_TYPES
