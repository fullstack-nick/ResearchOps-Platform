import { expect, test } from '@playwright/test';
import path from 'node:path';

test('uploads a synthetic invoice and opens the document workspace', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Operations dashboard' })).toBeVisible();

  await page.getByRole('link', { name: 'Upload document' }).first().click();
  await page.getByLabel('Workflow type').selectOption('procurement');

  const samplePath = path.resolve(
    process.cwd(),
    '..',
    'sample-documents',
    'procurement',
    'invoice_helix_lab_supplies.pdf',
  );
  await page.getByLabel('PDF document').setInputFiles(samplePath);
  await page.getByRole('button', { name: /Upload and create workflow/i }).click();

  await expect(page.getByRole('heading', { name: 'invoice_helix_lab_supplies.pdf' })).toBeVisible();
  const uploadedDocumentUrl = new URL(page.url());
  await expect(page.getByTitle('Document preview')).toBeVisible();
  await expect(page.getByText('Showing page 1 of 1')).toBeVisible();
  const hasRenderedPixels = await page
    .getByTitle('Document preview')
    .evaluate((canvas: HTMLCanvasElement) => {
      const context = canvas.getContext('2d');
      if (!context || canvas.width === 0 || canvas.height === 0) return false;
      const data = context.getImageData(0, 0, canvas.width, canvas.height).data;
      for (let index = 0; index < data.length; index += 400) {
        if (data[index] < 245 || data[index + 1] < 245 || data[index + 2] < 245) {
          return true;
        }
      }
      return false;
    });
  expect(hasRenderedPixels).toBe(true);
  await expect(page.getByText('document.uploaded')).toBeVisible();

  await page.getByRole('link', { name: 'Back to queues' }).click();
  await expect(page.locator(`a[href="${uploadedDocumentUrl.pathname}"]`)).toBeVisible();
});
