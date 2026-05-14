export const workflowTypes = ['procurement', 'hr_onboarding', 'grants', 'contracts', 'reports'] as const;

export type WorkflowType = (typeof workflowTypes)[number];

export type WorkflowStep = {
  id: string;
  step_name: string;
  status: string;
  assigned_role: string;
  created_at: string;
};

export type Workflow = {
  id: string;
  workflow_type: WorkflowType;
  status: string;
  current_step: string;
  created_at: string;
  updated_at: string;
  steps: WorkflowStep[];
};

export type DocumentVersion = {
  id: string;
  version_number: number;
  size_bytes: number;
  sha256: string;
  created_at: string;
};

export type DocumentRecord = {
  id: string;
  owner_user_id: string;
  original_filename: string;
  safe_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  workflow_type: WorkflowType;
  status: string;
  created_at: string;
  updated_at: string;
  workflow: Workflow;
  versions: DocumentVersion[];
};

export type DocumentListResponse = {
  documents: DocumentRecord[];
};

export type UploadResponse = {
  document: DocumentRecord;
};

export type DashboardSummary = {
  total_documents: number;
  awaiting_review: number;
  documents_by_workflow: Array<{ workflow_type: WorkflowType; count: number }>;
  recent_failures: number;
  average_processing_seconds: number | null;
};

export type AuditEvent = {
  event_id: string;
  timestamp: string;
  actor_type: 'user' | 'agent' | 'system';
  actor_id: string | null;
  document_id: string | null;
  workflow_id: string | null;
  event_type: string;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
  reason: string | null;
  source_ip: string | null;
  correlation_id: string;
};

export type AuditEventListResponse = {
  audit_events: AuditEvent[];
};
