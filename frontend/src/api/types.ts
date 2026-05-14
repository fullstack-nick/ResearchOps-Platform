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
  storage_provider: string;
  storage_container: string | null;
  storage_object_key: string | null;
  size_bytes: number;
  sha256: string;
  created_at: string;
};

export type ExtractionSummary = {
  status: string;
  missing_field_count: number;
  latest_run_id: string | null;
  failed: boolean;
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
  extraction_summary: ExtractionSummary;
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
  documents_with_missing_fields: number;
  average_processing_seconds: number | null;
};

export type ExtractionRun = {
  id: string;
  document_id: string;
  document_version_id: string;
  status: string;
  model_id: string;
  missing_fields: string[];
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type ExtractedField = {
  id: string;
  field_key: string;
  label: string;
  value: string | null;
  display_value: string | null;
  value_type: string;
  confidence: number | null;
  source_page: number | null;
  source_regions: Array<Record<string, unknown>>;
  raw_value: Record<string, unknown> | null;
  is_missing: boolean;
  display_order: number;
  corrected_value: string | null;
  correction_reason: string | null;
  corrected_at: string | null;
};

export type ExtractedLineItem = {
  id: string;
  item_index: number;
  description: string | null;
  quantity: number | null;
  unit_price: number | null;
  amount: number | null;
  currency: string | null;
  confidence: number | null;
  source_page: number | null;
  source_regions: Array<Record<string, unknown>>;
  raw_value: Record<string, unknown> | null;
};

export type ExtractionResponse = {
  document_id: string;
  available: boolean;
  status: string;
  latest_run: ExtractionRun | null;
  fields: ExtractedField[];
  missing_fields: string[];
  line_items: ExtractedLineItem[];
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

export type IndexingRun = {
  id: string;
  document_id: string;
  document_version_id: string;
  status: string;
  read_model_id: string;
  embedding_model: string | null;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type DocumentChunk = {
  id: string;
  chunk_index: number;
  content: string;
  page_number: number | null;
  char_count: number;
};

export type IndexingResponse = {
  document_id: string;
  status: string;
  latest_run: IndexingRun | null;
  chunk_count: number;
  chunks: DocumentChunk[];
};

export type Citation = {
  chunk_id: string;
  page_number: number | null;
  content: string;
  score: number | null;
};

export type QuestionAnswer = {
  id: string;
  document_id: string;
  question: string;
  answer: string | null;
  status: string;
  citations: Citation[];
  model_id: string | null;
  error_message: string | null;
  created_at: string;
};

export type QuestionListResponse = {
  questions: QuestionAnswer[];
};
