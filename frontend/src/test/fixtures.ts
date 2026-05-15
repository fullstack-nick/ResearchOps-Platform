import type {
  AuditEventListResponse,
  AuthConfig,
  CurrentUser,
  DashboardSummary,
  DevUserListResponse,
  DocumentListResponse,
  DocumentRecord,
  ExtractionResponse,
  IndexingResponse,
  QuestionListResponse,
  WorkflowState,
} from '../api/types';

export const documentFixture: DocumentRecord = {
  id: '11111111-1111-4111-8111-111111111111',
  owner_user_id: '00000000-0000-4000-8000-000000000001',
  original_filename: 'invoice_helix_lab_supplies.pdf',
  safe_filename: 'invoice_helix_lab_supplies.pdf',
  content_type: 'application/pdf',
  size_bytes: 4582,
  sha256: 'a'.repeat(64),
  workflow_type: 'procurement',
  status: 'extracted',
  created_at: '2026-05-14T10:00:00Z',
  updated_at: '2026-05-14T10:00:00Z',
  workflow: {
    id: '22222222-2222-4222-8222-222222222222',
    workflow_type: 'procurement',
    status: 'awaiting_review',
    current_step: 'intake_review',
    created_at: '2026-05-14T10:00:00Z',
    updated_at: '2026-05-14T10:00:00Z',
    steps: [
      {
        id: '33333333-3333-4333-8333-333333333333',
        step_name: 'intake_review',
        status: 'pending',
        assigned_role: 'operations_admin',
        created_at: '2026-05-14T10:00:00Z',
      },
    ],
  },
  extraction_summary: {
    status: 'completed',
    missing_field_count: 1,
    latest_run_id: '66666666-6666-4666-8666-666666666666',
    failed: false,
  },
  versions: [
    {
      id: '44444444-4444-4444-8444-444444444444',
      version_number: 1,
      storage_provider: 'azure_blob',
      storage_container: 'test-documents',
      storage_object_key:
        'documents/11111111-1111-4111-8111-111111111111/versions/44444444-4444-4444-8444-444444444444/invoice_helix_lab_supplies.pdf',
      size_bytes: 4582,
      sha256: 'a'.repeat(64),
      created_at: '2026-05-14T10:00:00Z',
    },
  ],
};

export const dashboardFixture: DashboardSummary = {
  total_documents: 1,
  awaiting_review: 1,
  documents_by_workflow: [{ workflow_type: 'procurement', count: 1 }],
  recent_failures: 0,
  documents_with_missing_fields: 1,
  average_processing_seconds: null,
};

export const documentListFixture: DocumentListResponse = {
  documents: [documentFixture],
};

export const auditFixture: AuditEventListResponse = {
  audit_events: [
    {
      event_id: '55555555-5555-4555-8555-555555555555',
      timestamp: '2026-05-14T10:00:01Z',
      actor_type: 'user',
      actor_id: '00000000-0000-4000-8000-000000000001',
      document_id: documentFixture.id,
      workflow_id: documentFixture.workflow.id,
      event_type: 'document.uploaded',
      before_value: null,
      after_value: { filename: documentFixture.original_filename },
      reason: 'Phase 2 Azure Blob document intake',
      source_ip: '127.0.0.1',
      correlation_id: 'test-correlation',
    },
    {
      event_id: '77777777-7777-4777-8777-777777777777',
      timestamp: '2026-05-14T10:01:00Z',
      actor_type: 'system',
      actor_id: null,
      document_id: documentFixture.id,
      workflow_id: documentFixture.workflow.id,
      event_type: 'extraction.completed',
      before_value: null,
      after_value: { missing_fields: ['purchase_order_number'] },
      reason: 'Azure Document Intelligence extraction completed',
      source_ip: null,
      correlation_id: 'test-correlation',
    },
  ],
};

export const extractionFixture: ExtractionResponse = {
  document_id: documentFixture.id,
  available: true,
  status: 'completed',
  latest_run: {
    id: '66666666-6666-4666-8666-666666666666',
    document_id: documentFixture.id,
    document_version_id: '44444444-4444-4444-8444-444444444444',
    status: 'completed',
    model_id: 'prebuilt-invoice',
    missing_fields: ['purchase_order_number'],
    error_message: null,
    created_at: '2026-05-14T10:00:02Z',
    started_at: '2026-05-14T10:00:05Z',
    completed_at: '2026-05-14T10:00:12Z',
  },
  fields: [
    {
      id: '88000000-0000-4000-8000-000000000001',
      field_key: 'vendor_name',
      label: 'Vendor name',
      value: 'Helix Lab Supplies GmbH',
      display_value: 'Helix Lab Supplies GmbH',
      value_type: 'string',
      confidence: 0.99,
      source_page: 1,
      source_regions: [],
      raw_value: null,
      is_missing: false,
      display_order: 10,
      corrected_value: null,
      correction_reason: null,
      corrected_at: null,
    },
    {
      id: '88000000-0000-4000-8000-000000000002',
      field_key: 'gross_total',
      label: 'Gross total',
      value: '4010.30',
      display_value: '4010.30',
      value_type: 'currency',
      confidence: 0.98,
      source_page: 1,
      source_regions: [],
      raw_value: null,
      is_missing: false,
      display_order: 80,
      corrected_value: null,
      correction_reason: null,
      corrected_at: null,
    },
    {
      id: '88000000-0000-4000-8000-000000000003',
      field_key: 'purchase_order_number',
      label: 'Purchase order number',
      value: null,
      display_value: null,
      value_type: 'string',
      confidence: null,
      source_page: null,
      source_regions: [],
      raw_value: null,
      is_missing: true,
      display_order: 90,
      corrected_value: null,
      correction_reason: null,
      corrected_at: null,
    },
  ],
  missing_fields: ['purchase_order_number'],
  line_items: [
    {
      id: '99000000-0000-4000-8000-000000000001',
      item_index: 0,
      description: 'Single-cell reagent kit',
      quantity: 2,
      unit_price: 1200,
      amount: 2400,
      currency: 'EUR',
      confidence: 0.92,
      source_page: 1,
      source_regions: [],
      raw_value: null,
    },
  ],
};

export const indexingFixture: IndexingResponse = {
  document_id: documentFixture.id,
  status: 'completed',
  latest_run: {
    id: 'aa000000-0000-4000-8000-000000000001',
    document_id: documentFixture.id,
    document_version_id: '44444444-4444-4444-8444-444444444444',
    status: 'completed',
    read_model_id: 'prebuilt-read',
    embedding_model: 'text-embedding-3-small',
    chunk_count: 2,
    error_message: null,
    created_at: '2026-05-14T10:00:03Z',
    started_at: '2026-05-14T10:00:06Z',
    completed_at: '2026-05-14T10:00:14Z',
  },
  chunk_count: 2,
  chunks: [
    {
      id: 'bb000000-0000-4000-8000-000000000001',
      chunk_index: 0,
      content: 'Helix Lab Supplies GmbH invoice HLS-2026-0142. Invoice total 4010.30 EUR.',
      page_number: 1,
      char_count: 72,
    },
    {
      id: 'bb000000-0000-4000-8000-000000000002',
      chunk_index: 1,
      content: 'Payment terms are net 14 days from the invoice issue date.',
      page_number: 2,
      char_count: 58,
    },
  ],
};

export const currentUserFixture: CurrentUser = {
  id: '00000000-0000-4000-8000-000000000001',
  email: 'demo.researchops@example.test',
  display_name: 'Demo Operations User',
  research_group: 'operations',
  is_active: true,
  roles: ['operations_admin', 'researcher'],
};

export const authConfigFixture: AuthConfig = {
  auth_mode: 'development',
  entra_client_id: null,
  entra_authority: null,
  entra_required_scope: 'access_as_user',
};

export const devUsersFixture: DevUserListResponse = {
  users: [
    {
      email: 'demo.researchops@example.test',
      display_name: 'Demo Operations User',
      research_group: 'operations',
      roles: ['operations_admin', 'researcher'],
    },
    {
      email: 'researcher.alice@example.test',
      display_name: 'Alice Researcher',
      research_group: 'genomics',
      roles: ['researcher'],
    },
    {
      email: 'lead.bob@example.test',
      display_name: 'Bob Group Lead',
      research_group: 'genomics',
      roles: ['group_lead'],
    },
    {
      email: 'finance.carol@example.test',
      display_name: 'Carol Finance',
      research_group: 'operations',
      roles: ['finance'],
    },
  ],
};

export const workflowStateFixture: WorkflowState = {
  id: documentFixture.workflow.id,
  document_id: documentFixture.id,
  workflow_type: 'procurement',
  status: 'awaiting_review',
  current_step: 'intake_review',
  research_group: 'genomics',
  created_at: '2026-05-14T10:00:00Z',
  updated_at: '2026-05-14T10:00:00Z',
  steps: [
    {
      id: '33333333-3333-4333-8333-333333333333',
      step_name: 'intake_review',
      status: 'pending',
      assigned_role: 'operations_admin',
      step_order: 0,
      completed_at: null,
      created_at: '2026-05-14T10:00:00Z',
      approvals: [],
    },
    {
      id: '33333333-3333-4333-8333-333333333334',
      step_name: 'group_lead_approval',
      status: 'pending',
      assigned_role: 'group_lead',
      step_order: 1,
      completed_at: null,
      created_at: '2026-05-14T10:00:00Z',
      approvals: [],
    },
    {
      id: '33333333-3333-4333-8333-333333333335',
      step_name: 'finance_approval',
      status: 'pending',
      assigned_role: 'finance',
      step_order: 2,
      completed_at: null,
      created_at: '2026-05-14T10:00:00Z',
      approvals: [],
    },
  ],
  pending_step_id: '33333333-3333-4333-8333-333333333333',
  can_decide_current_step: true,
};

export const questionsFixture: QuestionListResponse = {
  questions: [
    {
      id: 'cc000000-0000-4000-8000-000000000001',
      document_id: documentFixture.id,
      question: 'What is the invoice total?',
      answer: 'Based on [Source 1]: the invoice total is 4010.30 EUR.',
      status: 'completed',
      citations: [
        {
          chunk_id: `${documentFixture.id}_0`,
          page_number: 1,
          content: 'Helix Lab Supplies GmbH invoice HLS-2026-0142. Invoice total 4010.30 EUR.',
          score: 0.95,
        },
      ],
      model_id: 'gpt-4o-mini',
      error_message: null,
      created_at: '2026-05-14T10:05:00Z',
    },
  ],
};
