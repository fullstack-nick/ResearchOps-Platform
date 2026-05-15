import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const documentId = '11111111-1111-4111-8111-111111111111';
const workflowId = '22222222-2222-4222-8222-222222222222';
const versionId = '44444444-4444-4444-8444-444444444444';
const intakeStepId = '33333333-3333-4333-8333-333333333333';
const groupLeadStepId = '33333333-3333-4333-8333-333333333334';

function devUsersResponse() {
  return {
    users: [
      {
        email: 'admin.frank@example.test',
        display_name: 'Frank Admin',
        research_group: 'operations',
        roles: ['operations_admin', 'system_admin'],
      },
      {
        email: 'researcher.alice@example.test',
        display_name: 'Alice Researcher',
        research_group: 'genomics',
        roles: ['researcher'],
      },
    ],
  };
}

function userResponse(email: string) {
  if (email === 'admin.frank@example.test') {
    return {
      id: '00000000-0000-4000-8000-000000000206',
      email,
      display_name: 'Frank Admin',
      research_group: 'operations',
      is_active: true,
      roles: ['operations_admin', 'system_admin'],
    };
  }
  return {
    id: '00000000-0000-4000-8000-000000000201',
    email: 'researcher.alice@example.test',
    display_name: 'Alice Researcher',
    research_group: 'genomics',
    is_active: true,
    roles: ['researcher'],
  };
}

function documentRecord() {
  return {
    id: documentId,
    owner_user_id: '00000000-0000-4000-8000-000000000206',
    original_filename: 'invoice_helix_lab_supplies.pdf',
    safe_filename: 'invoice_helix_lab_supplies.pdf',
    content_type: 'application/pdf',
    size_bytes: 4582,
    sha256: 'a'.repeat(64),
    workflow_type: 'procurement',
    status: 'extracted',
    research_group: 'operations',
    created_at: '2026-05-14T10:00:00Z',
    updated_at: '2026-05-14T10:00:00Z',
    workflow: {
      id: workflowId,
      workflow_type: 'procurement',
      status: 'awaiting_review',
      current_step: 'intake_review',
      created_at: '2026-05-14T10:00:00Z',
      updated_at: '2026-05-14T10:00:00Z',
      steps: [
        {
          id: intakeStepId,
          step_name: 'intake_review',
          status: 'pending',
          assigned_role: 'operations_admin',
          step_order: 0,
          completed_at: null,
          created_at: '2026-05-14T10:00:00Z',
        },
      ],
    },
    extraction_summary: {
      status: 'completed',
      missing_field_count: 0,
      latest_run_id: 'extraction-run-id',
      failed: false,
    },
    versions: [
      {
        id: versionId,
        version_number: 1,
        storage_provider: 'azure_blob',
        storage_container: 'test-documents',
        storage_object_key: `documents/${documentId}/versions/${versionId}/invoice_helix_lab_supplies.pdf`,
        size_bytes: 4582,
        sha256: 'a'.repeat(64),
        created_at: '2026-05-14T10:00:00Z',
      },
    ],
  };
}

function workflowState(intakeApproved: boolean) {
  return {
    id: workflowId,
    document_id: documentId,
    workflow_type: 'procurement',
    status: 'awaiting_review',
    current_step: intakeApproved ? 'group_lead_approval' : 'intake_review',
    research_group: 'operations',
    created_at: '2026-05-14T10:00:00Z',
    updated_at: '2026-05-14T10:00:00Z',
    steps: [
      {
        id: intakeStepId,
        step_name: 'intake_review',
        status: intakeApproved ? 'completed' : 'pending',
        assigned_role: 'operations_admin',
        step_order: 0,
        completed_at: intakeApproved ? '2026-05-14T10:10:00Z' : null,
        created_at: '2026-05-14T10:00:00Z',
        approvals: intakeApproved
          ? [
              {
                id: 'aa-1',
                workflow_id: workflowId,
                workflow_step_id: intakeStepId,
                approver_user_id: '00000000-0000-4000-8000-000000000206',
                decision: 'approved',
                reason: 'intake complete',
                created_at: '2026-05-14T10:10:00Z',
              },
            ]
          : [],
      },
      {
        id: groupLeadStepId,
        step_name: 'group_lead_approval',
        status: 'pending',
        assigned_role: 'group_lead',
        step_order: 1,
        completed_at: null,
        created_at: '2026-05-14T10:00:00Z',
        approvals: [],
      },
    ],
    pending_step_id: intakeApproved ? groupLeadStepId : intakeStepId,
    can_decide_current_step: !intakeApproved,
  };
}

const auditEvents = [
  {
    event_id: '55555555-5555-4555-8555-555555555555',
    timestamp: '2026-05-14T10:00:01Z',
    actor_type: 'user',
    actor_id: '00000000-0000-4000-8000-000000000206',
    document_id: documentId,
    workflow_id: workflowId,
    event_type: 'document.uploaded',
    before_value: null,
    after_value: {},
    reason: 'Phase 2 Azure Blob document intake',
    source_ip: '127.0.0.1',
    correlation_id: 'test-correlation',
  },
];

test('admin signs in, sees the dashboard, and approves an intake step', async ({ page }) => {
  let approved = false;
  const samplePath = path.resolve(
    process.cwd(),
    '..',
    'sample-documents',
    'procurement',
    'invoice_helix_lab_supplies.pdf',
  );
  const pdfBytes = fs.readFileSync(samplePath);

  await page.route(/\/api\/documents\/[^/]+\/file$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/pdf',
      headers: { 'Content-Disposition': 'inline; filename="invoice_helix_lab_supplies.pdf"' },
      body: pdfBytes,
    });
  });

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    const headers = request.headers();
    const devEmail = headers['x-dev-user-email'] ?? 'admin.frank@example.test';

    if (pathname === '/api/auth/config') {
      await route.fulfill({
        json: {
          auth_mode: 'development',
          entra_client_id: null,
          entra_authority: null,
          entra_required_scope: 'access_as_user',
        },
      });
      return;
    }
    if (pathname === '/api/auth/me') {
      await route.fulfill({ json: userResponse(devEmail) });
      return;
    }
    if (pathname === '/api/auth/dev-users') {
      await route.fulfill({ json: devUsersResponse() });
      return;
    }
    if (
      pathname === `/api/workflows/${workflowId}/steps/${intakeStepId}/decision`
      && request.method() === 'POST'
    ) {
      approved = true;
      await route.fulfill({ json: workflowState(true) });
      return;
    }
    if (pathname === `/api/workflows/${workflowId}`) {
      await route.fulfill({ json: workflowState(approved) });
      return;
    }
    if (pathname === '/api/dashboard/summary') {
      await route.fulfill({
        json: {
          total_documents: 1,
          awaiting_review: 1,
          documents_by_workflow: [{ workflow_type: 'procurement', count: 1 }],
          recent_failures: 0,
          documents_with_missing_fields: 0,
          average_processing_seconds: null,
        },
      });
      return;
    }
    if (pathname === `/api/documents/${documentId}`) {
      await route.fulfill({ json: documentRecord() });
      return;
    }
    if (pathname === '/api/audit-events') {
      await route.fulfill({ json: { audit_events: auditEvents } });
      return;
    }
    if (pathname === `/api/documents/${documentId}/extraction`) {
      await route.fulfill({
        json: {
          document_id: documentId,
          available: true,
          status: 'completed',
          latest_run: null,
          fields: [],
          missing_fields: [],
          line_items: [],
        },
      });
      return;
    }
    if (pathname === `/api/documents/${documentId}/indexing`) {
      await route.fulfill({
        json: {
          document_id: documentId,
          status: 'completed',
          latest_run: null,
          chunk_count: 0,
          chunks: [],
        },
      });
      return;
    }
    if (pathname === `/api/documents/${documentId}/questions`) {
      await route.fulfill({ json: { questions: [] } });
      return;
    }
    await route.fallback();
  });

  await page.goto('/login');
  await expect(page.getByText('Sign in to ResearchOps')).toBeVisible();
  await page.getByRole('button', { name: /Frank Admin/ }).click();

  await expect(page.getByRole('heading', { name: 'Operations dashboard' })).toBeVisible();
  await expect(page.getByText('Frank Admin')).toBeVisible();
  await expect(page.getByText('operations admin').first()).toBeVisible();

  await page.goto(`/documents/${documentId}`);
  await expect(page.getByRole('heading', { name: 'Approval workflow' })).toBeVisible();
  await expect(page.getByText('intake review').first()).toBeVisible();

  await page.getByLabel('Decision reason').fill('intake complete');
  await page.getByRole('button', { name: 'Approve step' }).click();

  await expect(page.getByText(/Approved/).first()).toBeVisible();
  await expect(page.getByText('group lead approval')).toBeVisible();
});
