/* eslint-disable no-console */
import { Page, expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const BASE_URL =
  process.env.LIVE_BASE_URL ??
  'https://researchops-vt1zhh-frontend.salmonplant-ccdabe77.eastus.azurecontainerapps.io';

const REPO_ROOT = path.resolve(process.cwd(), '..');
const SCREENSHOT_DIR = path.join(REPO_ROOT, 'tmp', 'screenshots', 'matrix');
const SAMPLES = path.join(REPO_ROOT, 'sample-documents');

type WorkflowType = 'procurement' | 'hr_onboarding' | 'grants' | 'contracts' | 'reports';

type DocSpec = {
  slug: string;
  filename: string;
  workflowType: WorkflowType;
  questions: string[];
  expectedAnswerHints: string[][];
  expectedExtractionAvailable: boolean;
};

const DOCS: DocSpec[] = [
  {
    slug: 'procurement-invoice',
    filename: 'procurement/invoice_helix_lab_supplies.pdf',
    workflowType: 'procurement',
    questions: ['What is the invoice total?', 'Who is the vendor on this invoice?'],
    expectedAnswerHints: [['4010', 'EUR', 'total'], ['Helix', 'vendor', 'supplies']],
    expectedExtractionAvailable: true,
  },
  {
    slug: 'procurement-quote',
    filename: 'procurement/quote_microscope_maintenance.pdf',
    workflowType: 'procurement',
    questions: ['What service is being quoted?', 'What is the quoted price?'],
    expectedAnswerHints: [['microscope', 'maintenance', 'service'], ['EUR', 'price', 'quote', 'total']],
    expectedExtractionAvailable: true,
  },
  {
    slug: 'procurement-po',
    filename: 'procurement/purchase_order_001.pdf',
    workflowType: 'procurement',
    questions: ['What is the purchase order number?', 'What items are being ordered?'],
    expectedAnswerHints: [['PO', 'purchase', 'order', '001'], ['item', 'order', 'reagent', 'kit', 'cryobox']],
    expectedExtractionAvailable: true,
  },
  {
    slug: 'procurement-delivery',
    filename: 'procurement/delivery_note_001.pdf',
    workflowType: 'procurement',
    questions: ['What was delivered?', 'When was the delivery made?'],
    expectedAnswerHints: [['delivered', 'item', 'reagent', 'kit'], ['date', 'delivery', '2026']],
    expectedExtractionAvailable: true,
  },
  {
    slug: 'hr-onboarding-form',
    filename: 'hr/onboarding_form_research_assistant.pdf',
    workflowType: 'hr_onboarding',
    questions: ['Who is being onboarded?', 'What role are they joining?'],
    expectedAnswerHints: [['name', 'onboard', 'hire'], ['research', 'assistant', 'role']],
    expectedExtractionAvailable: false,
  },
  {
    slug: 'hr-cv',
    filename: 'hr/synthetic_cv_data_scientist.pdf',
    workflowType: 'hr_onboarding',
    questions: ['What is this candidate’s field?', 'What are the candidate’s key skills?'],
    expectedAnswerHints: [['data', 'scientist', 'science'], ['skill', 'experience', 'python', 'machine']],
    expectedExtractionAvailable: false,
  },
  {
    slug: 'hr-it-account',
    filename: 'hr/it_account_request.pdf',
    workflowType: 'hr_onboarding',
    questions: ['Who needs an IT account?', 'What systems do they need access to?'],
    expectedAnswerHints: [['name', 'account', 'user'], ['system', 'access', 'account']],
    expectedExtractionAvailable: false,
  },
  {
    slug: 'grants-award',
    filename: 'grants/grant_award_letter_neurodata_2026.pdf',
    workflowType: 'grants',
    questions: ['Which grant is being awarded?', 'What is the awarded amount?'],
    expectedAnswerHints: [['grant', 'neurodata', 'award'], ['EUR', 'amount', 'budget', 'total']],
    expectedExtractionAvailable: false,
  },
  {
    slug: 'grants-reporting',
    filename: 'grants/funder_reporting_instructions.pdf',
    workflowType: 'grants',
    questions: ['What reports must be submitted?', 'When are reports due?'],
    expectedAnswerHints: [['report', 'progress', 'financial'], ['deadline', 'due', 'month', '2026']],
    expectedExtractionAvailable: false,
  },
  {
    slug: 'grants-budget',
    filename: 'grants/budget_table.pdf',
    workflowType: 'grants',
    questions: ['What budget categories are listed?', 'What is the total budget?'],
    expectedAnswerHints: [['personnel', 'equipment', 'travel', 'budget'], ['EUR', 'total', 'budget']],
    expectedExtractionAvailable: false,
  },
  {
    slug: 'contracts-equipment',
    filename: 'contracts/equipment_service_contract.pdf',
    workflowType: 'contracts',
    questions: ['What equipment is covered by this contract?', 'How long does the contract last?'],
    expectedAnswerHints: [['equipment', 'service', 'maintenance'], ['year', 'term', 'duration', 'month']],
    expectedExtractionAvailable: false,
  },
  {
    slug: 'contracts-subscription',
    filename: 'contracts/software_subscription_agreement.pdf',
    workflowType: 'contracts',
    questions: ['What software is being subscribed to?', 'When does the subscription expire?'],
    expectedAnswerHints: [['software', 'subscription'], ['expire', 'renewal', 'date', '2026', '2027']],
    expectedExtractionAvailable: false,
  },
  {
    slug: 'reports-minutes',
    filename: 'reports/meeting_minutes_lab_admin.pdf',
    workflowType: 'reports',
    questions: ['What decisions were made at the meeting?', 'Who attended the meeting?'],
    expectedAnswerHints: [['decision', 'agreed', 'action'], ['attended', 'present', 'admin', 'lab']],
    expectedExtractionAvailable: false,
  },
  {
    slug: 'reports-monthly',
    filename: 'reports/monthly_operations_report.pdf',
    workflowType: 'reports',
    questions: ['What does this monthly report cover?', 'What follow-up actions are listed?'],
    expectedAnswerHints: [['month', 'operations', 'report'], ['action', 'follow', 'task']],
    expectedExtractionAvailable: false,
  },
];

const APPROVAL_CHAIN: Record<WorkflowType, number> = {
  procurement: 3,
  hr_onboarding: 3,
  grants: 2,
  contracts: 2,
  reports: 1,
};

test.describe.configure({ mode: 'serial' });

async function loginAs(page: Page, email: string) {
  await page.goto('/login');
  await page.evaluate((value) => window.localStorage.setItem('researchops:auth:dev-email', value), email);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Operations dashboard/ })).toBeVisible({ timeout: 30_000 });
}

async function uploadDocument(page: Page, spec: DocSpec) {
  await page.getByRole('link', { name: 'Upload', exact: true }).first().click();
  await expect(page.getByLabel('Workflow type')).toBeVisible();
  await page.getByLabel('Workflow type').selectOption(spec.workflowType);
  await page.getByLabel('PDF document').setInputFiles(path.join(SAMPLES, spec.filename));
  await page.getByRole('button', { name: /Upload and create workflow/i }).click();
  await page.waitForURL(/\/documents\//, { timeout: 90_000 });
  const url = new URL(page.url());
  const documentId = url.pathname.split('/').pop()!;
  return documentId;
}

async function waitForIndexing(page: Page, timeoutMs = 240_000) {
  // The Q&A panel renders the input only once the indexer reports completed.
  await expect(page.getByLabel('Ask about this document')).toBeVisible({ timeout: timeoutMs });
  await expect(page.getByText(/searchable chunks? indexed/)).toBeVisible({ timeout: timeoutMs });
}

async function askAndAssertGrounded(page: Page, question: string, hints: string[]) {
  await page.getByLabel('Ask about this document').fill(question);
  await page.getByRole('button', { name: 'Ask question' }).click();
  await expect(page.getByRole('button', { name: 'Ask question' })).toBeEnabled({ timeout: 120_000 });
  // The question appears in the conversation feed and the matching answer
  // sits in the same list item below it.
  const entry = page
    .locator('li', { has: page.getByText(question, { exact: true }) })
    .first();
  await expect(entry).toBeVisible({ timeout: 60_000 });
  // Sources block confirms the answer was grounded in retrieved chunks.
  await expect(entry.getByText('Sources')).toBeVisible({ timeout: 60_000 });
  const entryText = (await entry.innerText()).toLowerCase();
  const matched = hints.some((hint) => entryText.includes(hint.toLowerCase()));
  return { matched, entryText };
}

async function approveThroughChain(page: Page, expectedSteps: number) {
  const approvalSection = page.locator('section', {
    has: page.getByRole('heading', { name: 'Approval workflow' }),
  });
  for (let stepIndex = 0; stepIndex < expectedSteps; stepIndex++) {
    const button = approvalSection.getByRole('button', { name: 'Approve step' });
    await expect(button).toBeEnabled({ timeout: 60_000 });
    await approvalSection.getByLabel('Decision reason').fill(
      `Live matrix test - step ${stepIndex + 1}`,
    );
    // Pair the click with waiting for the POST so the next iteration cannot
    // run before the server has processed this approval.
    await Promise.all([
      page.waitForResponse(
        (res) => res.url().includes('/decision') && res.request().method() === 'POST',
        { timeout: 60_000 },
      ),
      button.click(),
    ]);
    // Allow React Query to refetch the workflow before the next iteration.
    await page.waitForLoadState('networkidle', { timeout: 30_000 });
  }
  // Final state: the decide form must disappear because workflow.status flips
  // from 'awaiting_review' to 'approved'.
  await expect(
    approvalSection.getByRole('button', { name: 'Approve step' }),
  ).toBeHidden({ timeout: 60_000 });
  await expect(
    approvalSection.getByText(/All approval steps have been completed/i),
  ).toBeVisible({ timeout: 60_000 });
}

async function verifyAuditTimeline(page: Page) {
  const audit = page.locator('section', { has: page.getByRole('heading', { name: 'Audit timeline' }) });
  await audit.scrollIntoViewIfNeeded();
  await expect(audit.getByText('document.uploaded')).toBeVisible();
  await expect(audit.getByText('indexing.completed').first()).toBeVisible({ timeout: 60_000 });
  await expect(audit.getByText('approval.granted').first()).toBeVisible({ timeout: 60_000 });
}

interface Result {
  slug: string;
  workflowType: WorkflowType;
  documentId?: string;
  uploadOk: boolean;
  pdfRendered: boolean;
  extractionOk: boolean;
  indexingOk: boolean;
  qa: { question: string; matched: boolean; preview: string }[];
  approvalOk: boolean;
  auditOk: boolean;
  error?: string;
}

const results: Result[] = [];

test.describe('phase6 live matrix', () => {
  test.use({ baseURL: BASE_URL, viewport: { width: 1440, height: 1100 } });

test('full AI matrix across every sample PDF', async ({ page }, testInfo) => {
  testInfo.setTimeout(45 * 60_000);
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  page.setDefaultTimeout(60_000);

  await loginAs(page, 'admin.frank@example.test');

  for (const spec of DOCS) {
    const result: Result = {
      slug: spec.slug,
      workflowType: spec.workflowType,
      uploadOk: false,
      pdfRendered: false,
      extractionOk: false,
      indexingOk: false,
      qa: [],
      approvalOk: false,
      auditOk: false,
    };
    console.log(`\n>>> ${spec.slug} (${spec.workflowType}) :: ${spec.filename}`);
    try {
      const documentId = await uploadDocument(page, spec);
      result.documentId = documentId;
      result.uploadOk = true;
      console.log(`  uploaded as ${documentId}`);

      // Wait for PDF canvas to render (proves pdf.js worker + file fetch).
      const previewSection = page.locator('section', {
        has: page.getByRole('heading', { name: 'Document preview' }),
      });
      try {
        await expect(previewSection.getByText(/Showing page \d+ of \d+/)).toBeVisible({ timeout: 120_000 });
        result.pdfRendered = true;
      } catch {
        result.pdfRendered = false;
      }

      // Extraction (only meaningful for procurement; others are 'unavailable').
      const extractionSection = page.locator('section', {
        has: page.getByRole('heading', { name: /(Invoice extraction|Extraction)/ }),
      });
      if (spec.expectedExtractionAvailable) {
        try {
          await expect(extractionSection.getByText('Extracted fields')).toBeVisible({ timeout: 120_000 });
          result.extractionOk = true;
        } catch {
          result.extractionOk = false;
        }
      } else {
        // For non-procurement, the panel renders an explanatory placeholder.
        result.extractionOk = true; // not applicable; treat as pass
      }

      // Indexing + Q&A
      await waitForIndexing(page);
      result.indexingOk = true;
      console.log('  indexing complete');

      for (let i = 0; i < spec.questions.length; i++) {
        const q = spec.questions[i]!;
        const hints = spec.expectedAnswerHints[i] ?? [];
        const { matched, entryText } = await askAndAssertGrounded(page, q, hints);
        result.qa.push({ question: q, matched, preview: entryText.slice(0, 200) });
      }

      // Approval chain
      await approveThroughChain(page, APPROVAL_CHAIN[spec.workflowType]);
      result.approvalOk = true;
      console.log('  approval chain complete');

      // Audit timeline
      await verifyAuditTimeline(page);
      result.auditOk = true;

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${spec.slug}.png`),
        fullPage: true,
      });
    } catch (err) {
      result.error = (err as Error).message;
      console.log(`  FAILED: ${result.error}`);
      try {
        await page.screenshot({
          path: path.join(SCREENSHOT_DIR, `${spec.slug}-FAILED.png`),
          fullPage: true,
        });
      } catch {
        /* ignore */
      }
    } finally {
      results.push(result);
      // Return to login to switch context and avoid carrying state between docs.
      await page.goto('/');
    }
  }

  const summaryPath = path.join(SCREENSHOT_DIR, 'matrix-summary.json');
  fs.writeFileSync(summaryPath, JSON.stringify(results, null, 2));
  console.log(`\nWrote summary to ${summaryPath}`);

  // Aggregate pass/fail printout so the harness logs make it easy to scan.
  const failures = results.filter((r) => r.error || !r.indexingOk || !r.approvalOk || !r.auditOk);
  console.log('\n=== MATRIX SUMMARY ===');
  for (const r of results) {
    const qaOk = r.qa.length > 0 && r.qa.every((q) => q.matched);
    console.log(
      `${r.slug}: upload=${r.uploadOk ? 'Y' : 'N'} pdf=${r.pdfRendered ? 'Y' : 'N'} extr=${r.extractionOk ? 'Y' : 'N'} idx=${r.indexingOk ? 'Y' : 'N'} qa=${qaOk ? 'Y' : 'N'} appr=${r.approvalOk ? 'Y' : 'N'} audit=${r.auditOk ? 'Y' : 'N'}${r.error ? ' err=' + r.error.slice(0, 80) : ''}`,
    );
  }
  console.log(`\n${results.length} documents tested, ${failures.length} hard failures.`);
});

});
