import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const documentId = '11111111-1111-4111-8111-111111111111';
const workflowId = '22222222-2222-4222-8222-222222222222';
const versionId = '44444444-4444-4444-8444-444444444444';
const purchaseOrderFieldId = '88000000-0000-4000-8000-000000000003';

function documentRecord(status = 'extracted') {
  return {
    id: documentId,
    owner_user_id: '00000000-0000-4000-8000-000000000001',
    original_filename: 'invoice_helix_lab_supplies.pdf',
    safe_filename: 'invoice_helix_lab_supplies.pdf',
    content_type: 'application/pdf',
    size_bytes: 4582,
    sha256: 'a'.repeat(64),
    workflow_type: 'procurement',
    status,
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
      missing_field_count: 1,
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

test('uploads a synthetic invoice and reviews Azure extraction results', async ({ page }) => {
  let uploaded = false;
  let correctedPurchaseOrder: string | null = null;
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
    const url = new URL(request.url());
    const pathname = url.pathname;

    if (pathname === '/api/dashboard/summary') {
      await route.fulfill({
        json: {
          total_documents: uploaded ? 1 : 0,
          awaiting_review: uploaded ? 1 : 0,
          documents_by_workflow: uploaded ? [{ workflow_type: 'procurement', count: 1 }] : [],
          recent_failures: 0,
          documents_with_missing_fields: uploaded && !correctedPurchaseOrder ? 1 : 0,
          average_processing_seconds: null,
        },
      });
      return;
    }

    if (pathname === '/api/documents' && request.method() === 'POST') {
      uploaded = true;
      await route.fulfill({ status: 201, json: { document: documentRecord('extraction_pending') } });
      return;
    }

    if (pathname === '/api/documents') {
      await route.fulfill({ json: { documents: uploaded ? [documentRecord()] : [] } });
      return;
    }

    if (pathname === `/api/documents/${documentId}`) {
      await route.fulfill({ json: documentRecord() });
      return;
    }

    if (pathname === `/api/documents/${documentId}/extraction`) {
      await route.fulfill({ json: extractionResponse(correctedPurchaseOrder) });
      return;
    }

    if (pathname === `/api/documents/${documentId}/fields/${purchaseOrderFieldId}`) {
      correctedPurchaseOrder = 'PO-2026-001';
      await route.fulfill({
        json: {
          ...extractionResponse(correctedPurchaseOrder).fields[2]!,
          corrected_value: correctedPurchaseOrder,
          display_value: correctedPurchaseOrder,
          is_missing: false,
        },
      });
      return;
    }

    if (pathname === '/api/audit-events') {
      await route.fulfill({ json: auditEvents(correctedPurchaseOrder !== null) });
      return;
    }

    await route.fallback();
  });

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Operations dashboard' })).toBeVisible();

  await page.getByRole('link', { name: 'Upload document' }).first().click();
  await page.getByLabel('Workflow type').selectOption('procurement');
  await page.getByLabel('PDF document').setInputFiles(samplePath);
  await page.getByRole('button', { name: /Upload and create workflow/i }).click();

  await expect(page.getByRole('heading', { name: 'invoice_helix_lab_supplies.pdf' })).toBeVisible();
  await expect(page.getByTitle('Document preview')).toBeVisible();
  await expect(page.getByText('Showing page 1 of 1')).toBeVisible();
  await expect(page.getByText('Helix Lab Supplies GmbH')).toBeVisible();
  await expect(page.getByText('4010.30')).toBeVisible();
  await expect(page.getByText('Single-cell reagent kit')).toBeVisible();
  await expect(page.getByText('Purchase order number').first()).toBeVisible();

  await page.getByRole('button', { name: 'Correct Purchase order number' }).click();
  await page.getByLabel('Corrected value').fill('PO-2026-001');
  await page.getByLabel('Reason').fill('Requester supplied it');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('PO-2026-001')).toBeVisible();
  await expect(page.getByText('field.corrected')).toBeVisible();

  await page.goto('/');
  await expect(page.getByText('Procurement')).toBeVisible();
  await expect(page.getByText('Missing fields')).toBeVisible();
});

function extractionResponse(correctedPurchaseOrder: string | null) {
  return {
    document_id: documentId,
    available: true,
    status: 'completed',
    latest_run: {
      id: '66666666-6666-4666-8666-666666666666',
      document_id: documentId,
      document_version_id: versionId,
      status: 'completed',
      model_id: 'prebuilt-invoice',
      missing_fields: correctedPurchaseOrder ? [] : ['purchase_order_number'],
      error_message: null,
      created_at: '2026-05-14T10:00:02Z',
      started_at: '2026-05-14T10:00:05Z',
      completed_at: '2026-05-14T10:00:12Z',
    },
    fields: [
      extractedField('88000000-0000-4000-8000-000000000001', 'vendor_name', 'Vendor name', 'Helix Lab Supplies GmbH', 0.99),
      extractedField('88000000-0000-4000-8000-000000000002', 'gross_total', 'Gross total', '4010.30', 0.98),
      {
        ...extractedField(
          purchaseOrderFieldId,
          'purchase_order_number',
          'Purchase order number',
          correctedPurchaseOrder,
          null,
        ),
        is_missing: correctedPurchaseOrder === null,
        corrected_value: correctedPurchaseOrder,
      },
    ],
    missing_fields: correctedPurchaseOrder ? [] : ['purchase_order_number'],
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
}

function extractedField(
  id: string,
  fieldKey: string,
  label: string,
  value: string | null,
  confidence: number | null,
) {
  return {
    id,
    field_key: fieldKey,
    label,
    value,
    display_value: value,
    value_type: 'string',
    confidence,
    source_page: 1,
    source_regions: [],
    raw_value: null,
    is_missing: value === null,
    display_order: 10,
    corrected_value: null,
    correction_reason: null,
    corrected_at: null,
  };
}

function auditEvents(includeCorrection: boolean) {
  const events = [
    {
      event_id: '55555555-5555-4555-8555-555555555555',
      timestamp: '2026-05-14T10:00:01Z',
      actor_type: 'user',
      actor_id: '00000000-0000-4000-8000-000000000001',
      document_id: documentId,
      workflow_id: workflowId,
      event_type: 'document.uploaded',
      before_value: null,
      after_value: { filename: 'invoice_helix_lab_supplies.pdf' },
      reason: 'Phase 2 Azure Blob document intake',
      source_ip: '127.0.0.1',
      correlation_id: 'test-correlation',
    },
    {
      event_id: '77777777-7777-4777-8777-777777777777',
      timestamp: '2026-05-14T10:01:00Z',
      actor_type: 'system',
      actor_id: null,
      document_id: documentId,
      workflow_id: workflowId,
      event_type: 'extraction.completed',
      before_value: null,
      after_value: { missing_fields: ['purchase_order_number'] },
      reason: 'Azure Document Intelligence extraction completed',
      source_ip: null,
      correlation_id: 'test-correlation',
    },
  ];
  if (includeCorrection) {
    events.unshift({
      event_id: '88888888-8888-4888-8888-888888888888',
      timestamp: '2026-05-14T10:02:00Z',
      actor_type: 'user',
      actor_id: '00000000-0000-4000-8000-000000000001',
      document_id: documentId,
      workflow_id: workflowId,
      event_type: 'field.corrected',
      before_value: { field_key: 'purchase_order_number' },
      after_value: { corrected_value: 'PO-2026-001' },
      reason: 'Requester supplied it',
      source_ip: '127.0.0.1',
      correlation_id: 'test-correlation',
    });
  }
  return { audit_events: events };
}
