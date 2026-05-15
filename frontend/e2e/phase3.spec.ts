import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const documentId = '11111111-1111-4111-8111-111111111111';
const workflowId = '22222222-2222-4222-8222-222222222222';
const versionId = '44444444-4444-4444-8444-444444444444';

function documentRecord() {
  return {
    id: documentId,
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
      id: workflowId,
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
      missing_field_count: 0,
      latest_run_id: '66666666-6666-4666-8666-666666666666',
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

const extractionResponse = {
  document_id: documentId,
  available: true,
  status: 'completed',
  latest_run: {
    id: '66666666-6666-4666-8666-666666666666',
    document_id: documentId,
    document_version_id: versionId,
    status: 'completed',
    model_id: 'prebuilt-invoice',
    missing_fields: [],
    error_message: null,
    created_at: '2026-05-14T10:00:02Z',
    started_at: '2026-05-14T10:00:05Z',
    completed_at: '2026-05-14T10:00:12Z',
  },
  fields: [],
  missing_fields: [],
  line_items: [],
};

const indexingResponse = {
  document_id: documentId,
  status: 'completed',
  latest_run: {
    id: 'aa000000-0000-4000-8000-000000000001',
    document_id: documentId,
    document_version_id: versionId,
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
      content: 'Helix Lab Supplies GmbH invoice. Invoice total 4010.30 EUR.',
      page_number: 1,
      char_count: 58,
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

const existingQuestion = {
  id: 'cc000000-0000-4000-8000-000000000001',
  document_id: documentId,
  question: 'What is the invoice total?',
  answer: 'Based on [Source 1]: the invoice total is 4010.30 EUR.',
  status: 'completed',
  citations: [
    {
      chunk_id: `${documentId}_0`,
      page_number: 1,
      content: 'Helix Lab Supplies GmbH invoice. Invoice total 4010.30 EUR.',
      score: 0.95,
    },
  ],
  model_id: 'gpt-4o-mini',
  error_message: null,
  created_at: '2026-05-14T10:05:00Z',
};

const askedQuestion = {
  id: 'cc000000-0000-4000-8000-000000000002',
  document_id: documentId,
  question: 'When is payment due?',
  answer: 'Based on [Source 1]: payment is due net 14 days from the invoice issue date.',
  status: 'completed',
  citations: [
    {
      chunk_id: `${documentId}_1`,
      page_number: 2,
      content: 'Payment terms are net 14 days from the invoice issue date.',
      score: 0.91,
    },
  ],
  model_id: 'gpt-4o-mini',
  error_message: null,
  created_at: '2026-05-14T10:06:00Z',
};

function auditEvents(includeQuestion: boolean) {
  const events = [
    {
      event_id: '99999999-9999-4999-8999-999999999999',
      timestamp: '2026-05-14T10:01:00Z',
      actor_type: 'system',
      actor_id: null,
      document_id: documentId,
      workflow_id: workflowId,
      event_type: 'indexing.completed',
      before_value: null,
      after_value: { chunk_count: 2 },
      reason: 'Azure AI Search indexing completed',
      source_ip: null,
      correlation_id: 'test-correlation',
    },
  ];
  if (includeQuestion) {
    events.unshift({
      event_id: 'a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1',
      timestamp: '2026-05-14T10:06:00Z',
      actor_type: 'user',
      actor_id: '00000000-0000-4000-8000-000000000001',
      document_id: documentId,
      workflow_id: workflowId,
      event_type: 'document.question_asked',
      before_value: null,
      after_value: { status: 'completed' },
      reason: 'When is payment due?',
      source_ip: '127.0.0.1',
      correlation_id: 'test-correlation',
    } as (typeof events)[number]);
  }
  return { audit_events: events };
}

test('reviews Azure AI Search indexing and asks a grounded question', async ({ page }) => {
  let asked = false;
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

    if (pathname === `/api/documents/${documentId}/questions` && request.method() === 'POST') {
      asked = true;
      await route.fulfill({ status: 201, json: askedQuestion });
      return;
    }
    if (pathname === `/api/documents/${documentId}/questions`) {
      await route.fulfill({
        json: { questions: asked ? [askedQuestion, existingQuestion] : [existingQuestion] },
      });
      return;
    }
    if (pathname === `/api/documents/${documentId}/indexing`) {
      await route.fulfill({ json: indexingResponse });
      return;
    }
    if (pathname === `/api/documents/${documentId}/extraction`) {
      await route.fulfill({ json: extractionResponse });
      return;
    }
    if (pathname === `/api/documents/${documentId}`) {
      await route.fulfill({ json: documentRecord() });
      return;
    }
    if (pathname === '/api/audit-events') {
      await route.fulfill({ json: auditEvents(asked) });
      return;
    }
    await route.fallback();
  });

  await page.goto(`/documents/${documentId}`);

  await expect(
    page.getByRole('heading', { name: 'invoice_helix_lab_supplies.pdf' }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Document Q&A' })).toBeVisible();
  await expect(page.getByText(/2 searchable chunks indexed/)).toBeVisible();
  await expect(page.getByText('What is the invoice total?')).toBeVisible();
  await expect(page.getByText(/the invoice total is 4010.30 EUR/)).toBeVisible();
  await expect(page.getByText(/Source 1 · page 1/)).toBeVisible();

  await page.getByLabel('Ask about this document').fill('When is payment due?');
  await page.getByRole('button', { name: 'Ask question' }).click();

  await expect(page.getByText('When is payment due?').first()).toBeVisible();
  await expect(page.getByText(/payment is due net 14 days/)).toBeVisible();
  await expect(page.getByText('document.question_asked')).toBeVisible();
});
