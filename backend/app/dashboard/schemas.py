from pydantic import BaseModel


class QueueCount(BaseModel):
    workflow_type: str
    count: int


class DashboardSummary(BaseModel):
    total_documents: int
    awaiting_review: int
    documents_by_workflow: list[QueueCount]
    recent_failures: int
    average_processing_seconds: float | None
