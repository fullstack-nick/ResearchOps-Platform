import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const BASE_URL =
  process.env.LIVE_BASE_URL ??
  'https://researchops-vt1zhh-frontend.salmonplant-ccdabe77.eastus.azurecontainerapps.io';

const REPO_ROOT = path.resolve(process.cwd(), '..');
const SCREENSHOT_DIR = path.join(REPO_ROOT, 'tmp', 'screenshots');
const SAMPLE_PDF = path.join(
  REPO_ROOT,
  'sample-documents',
  'procurement',
  'invoice_helix_lab_supplies.pdf',
);

test.use({ baseURL: BASE_URL, viewport: { width: 1440, height: 900 } });

test('captures every workflow against the live Azure deployment', async ({ page }, testInfo) => {
  testInfo.setTimeout(180_000);
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  // 1. Login page
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: /Sign in to ResearchOps/ })).toBeVisible();
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01-login.png'), fullPage: true });

  // Pick the operations admin persona so we can see everything
  await page.getByRole('button', { name: /Frank Admin/ }).click();

  // 2. Dashboard
  await page.waitForURL('**/');
  await expect(page.getByRole('heading', { name: /Operations dashboard/ })).toBeVisible();
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02-dashboard-admin.png'), fullPage: true });

  // 3. Upload page
  await page.getByRole('link', { name: 'Upload document' }).first().click();
  await expect(page.getByLabel('Workflow type')).toBeVisible();
  await page.getByLabel('Workflow type').selectOption('procurement');
  await page.getByLabel('PDF document').setInputFiles(SAMPLE_PDF);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03-upload-form.png'), fullPage: true });

  // 4. Submit upload — should navigate to document workspace
  await page.getByRole('button', { name: /Upload and create workflow/i }).click();
  await page.waitForURL(/\/documents\//, { timeout: 60_000 });
  await expect(page.getByRole('heading', { name: 'invoice_helix_lab_supplies.pdf' })).toBeVisible({
    timeout: 60_000,
  });
  await page.waitForTimeout(2_000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04-document-uploaded.png'), fullPage: true });

  // 5. Wait for Azure AI Document Intelligence extraction to complete
  await expect(page.getByRole('heading', { name: 'Invoice extraction' })).toBeVisible();
  await expect(page.locator('text=Extracted fields')).toBeVisible({ timeout: 120_000 });
  await page.waitForTimeout(2_000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05-extraction-completed.png'), fullPage: true });

  // 6. Approval panel
  await expect(page.getByRole('heading', { name: 'Approval workflow' })).toBeVisible();
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06-approval-panel.png'), fullPage: true });

  // 7. Approve the intake step
  await page.getByLabel('Decision reason').fill('Verified invoice intake in live demo run');
  await page.getByRole('button', { name: 'Approve step' }).click();
  await expect(page.getByText('group lead approval').first()).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(2_000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '07-approval-advanced.png'), fullPage: true });

  // 8. Q&A panel (wait for indexing to be ready)
  await expect(page.getByRole('heading', { name: /Document Q&A/ })).toBeVisible();
  await expect(page.getByLabel('Ask about this document')).toBeVisible({ timeout: 180_000 });
  await page.getByLabel('Ask about this document').fill('What is the invoice total?');
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '08-qa-question-ready.png'), fullPage: true });

  await page.getByRole('button', { name: 'Ask question' }).click();
  // Wait for the conversation entry to appear AND for the answer to load.
  // The Asking... button toggles back to "Ask question" once the answer is in.
  await expect(page.getByText('What is the invoice total?').first()).toBeVisible({ timeout: 90_000 });
  await expect(page.getByRole('button', { name: 'Ask question' })).toBeEnabled({ timeout: 120_000 });
  // The fixture answer mentions the EUR total; wait for "Sources" header which
  // only renders once citations are populated.
  await expect(page.getByText('Sources').first()).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(2_000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '09-qa-grounded-answer.png'), fullPage: true });

  // 10. Audit timeline
  await page.locator('text=Audit timeline').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '10-audit-timeline.png'), fullPage: true });

  // 11. Queue view
  await page.getByRole('link', { name: 'Queues' }).first().click();
  await page.waitForURL('**/queues');
  await expect(page.getByRole('heading', { name: 'All workflow queues' })).toBeVisible();
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '11-queues-all.png'), fullPage: true });

  // 12. Switch to researcher persona and verify they only see their own docs
  await page.getByRole('link', { name: /Switch identity/ }).click();
  await page.waitForURL('**/login');
  await page.getByRole('button', { name: /Alice Researcher/ }).click();
  await page.waitForURL('**/');
  await expect(page.getByRole('heading', { name: /Operations dashboard/ })).toBeVisible();
  await page.waitForTimeout(1_500);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '12-dashboard-researcher.png'), fullPage: true });
});
