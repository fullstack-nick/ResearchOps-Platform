from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: UUID
    timestamp: datetime
    actor_type: str
    actor_id: UUID | None
    document_id: UUID | None
    workflow_id: UUID | None
    event_type: str
    before_value: dict[str, Any] | None
    after_value: dict[str, Any] | None
    reason: str | None
    source_ip: str | None
    correlation_id: str


class AuditEventListResponse(BaseModel):
    audit_events: list[AuditEventRead]
