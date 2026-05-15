import { test } from '@playwright/test';

const BASE_URL = 'https://researchops-vt1zhh-frontend.salmonplant-ccdabe77.eastus.azurecontainerapps.io';

test.use({ baseURL: BASE_URL });

test('debug PDF preview failure', async ({ page }) => {
  test.setTimeout(120_000);

  const errors: string[] = [];
  const networkFailures: { url: string; status: number | string; ct?: string | null }[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      errors.push(`${msg.type()}: ${msg.text()}`);
    }
  });
  page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`));
  page.on('requestfailed', (req) => {
    networkFailures.push({ url: req.url(), status: req.failure()?.errorText ?? 'failed' });
  });
  page.on('response', async (res) => {
    if (
      res.url().includes('/file')
      || res.url().includes('.mjs')
      || res.url().includes('.wasm')
      || res.url().includes('pdf.worker')
    ) {
      networkFailures.push({
        url: res.url(),
        status: res.status(),
        ct: res.headers()['content-type'] ?? null,
      });
    }
  });

  await page.goto('/login');
  await page.getByRole('button', { name: /Frank Admin/ }).click();
  await page.waitForURL('**/');
  await page.getByRole('link', { name: 'Queues' }).click();
  await page.waitForURL('**/queues');
  await page.getByRole('link', { name: /invoice_helix_lab_supplies/ }).first().click();
  await page.waitForURL(/\/documents\//);
  await page.waitForTimeout(15_000);

  console.log('=== CONSOLE ERRORS ===');
  for (const e of errors) console.log(e);
  console.log('=== NETWORK ===');
  for (const n of networkFailures) console.log(JSON.stringify(n));
});
