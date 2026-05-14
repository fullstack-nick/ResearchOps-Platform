import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../App';
import { auditFixture, documentFixture } from '../test/fixtures';
import { renderWithProviders } from '../test/render';

describe('DocumentPage', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes('/api/audit-events')) {
          return new Response(JSON.stringify(auditFixture), { status: 200 });
        }
        return new Response(JSON.stringify(documentFixture), { status: 200 });
      }),
    );
  });

  it('renders preview, metadata, phase 2 placeholder, and audit timeline', async () => {
    renderWithProviders(<App />, `/documents/${documentFixture.id}`);

    expect(await screen.findByText('invoice_helix_lab_supplies.pdf')).toBeInTheDocument();
    expect(screen.getByTitle('Document preview')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open PDF' })).toHaveAttribute(
      'href',
      `http://localhost:8000/api/documents/${documentFixture.id}/file`,
    );
    expect(screen.getByText(/Not processed yet/)).toBeInTheDocument();
    expect(await screen.findByText('document.uploaded')).toBeInTheDocument();
  });
});
