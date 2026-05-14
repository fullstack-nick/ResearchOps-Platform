import type { AuditEventListResponse, DashboardSummary, DocumentListResponse, DocumentRecord } from '../api/types';

export const documentFixture: DocumentRecord = {
  id: '11111111-1111-4111-8111-111111111111',
  owner_user_id: '00000000-0000-4000-8000-000000000001',
  original_filename: 'invoice_helix_lab_supplies.pdf',
  safe_filename: 'invoice_helix_lab_supplies.pdf',
  content_type: 'application/pdf',
  size_bytes: 4582,
  sha256: 'a'.repeat(64),
  workflow_type: 'procurement',
  status: 'uploaded',
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
  versions: [
    {
      id: '44444444-4444-4444-8444-444444444444',
      version_number: 1,
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
      reason: 'Phase 1 local document intake',
      source_ip: '127.0.0.1',
      correlation_id: 'test-correlation',
    },
  ],
};
