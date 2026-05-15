import { fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../App';
import {
  auditFixture,
  authConfigFixture,
  currentUserFixture,
  documentFixture,
  extractionFixture,
  indexingFixture,
  questionsFixture,
  workflowStateFixture,
} from '../test/fixtures';
import { renderWithProviders } from '../test/render';

describe('DocumentPage', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes('/api/auth/me')) {
          return new Response(JSON.stringify(currentUserFixture), { status: 200 });
        }
        if (url.includes('/api/auth/config')) {
          return new Response(JSON.stringify(authConfigFixture), { status: 200 });
        }
        if (url.includes('/api/workflows')) {
          return new Response(JSON.stringify(workflowStateFixture), { status: 200 });
        }
        if (url.includes('/api/audit-events')) {
          return new Response(JSON.stringify(auditFixture), { status: 200 });
        }
        if (url.includes('/extraction')) {
          return new Response(JSON.stringify(extractionFixture), { status: 200 });
        }
        if (url.includes('/indexing')) {
          return new Response(JSON.stringify(indexingFixture), { status: 200 });
        }
        if (url.includes('/questions')) {
          return new Response(JSON.stringify(questionsFixture), { status: 200 });
        }
        return new Response(JSON.stringify(documentFixture), { status: 200 });
      }),
    );
  });

  it('renders preview, extraction fields, missing fields, line items, and audit timeline', async () => {
    renderWithProviders(<App />, `/documents/${documentFixture.id}`);

    expect(await screen.findByText('invoice_helix_lab_supplies.pdf')).toBeInTheDocument();
    expect(screen.getByTitle('Document preview')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open PDF' })).toHaveAttribute(
      'href',
      `http://localhost:8000/api/documents/${documentFixture.id}/file`,
    );
    expect(await screen.findByText('Helix Lab Supplies GmbH')).toBeInTheDocument();
    expect(screen.getByText('Gross total')).toBeInTheDocument();
    expect(screen.getByText('4010.30')).toBeInTheDocument();
    expect(screen.getAllByText('Purchase order number').length).toBeGreaterThan(0);
    expect(screen.getByText('Single-cell reagent kit')).toBeInTheDocument();
    expect(await screen.findByText('document.uploaded')).toBeInTheDocument();
    expect(await screen.findByText('extraction.completed')).toBeInTheDocument();
  });

  it('submits field corrections with a reason', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === 'PATCH') {
        return new Response(
          JSON.stringify({
            ...extractionFixture.fields[2]!,
            corrected_value: 'PO-2026-001',
            display_value: 'PO-2026-001',
            is_missing: false,
          }),
          { status: 200 },
        );
      }
      if (url.includes('/api/auth/me')) {
        return new Response(JSON.stringify(currentUserFixture), { status: 200 });
      }
      if (url.includes('/api/auth/config')) {
        return new Response(JSON.stringify(authConfigFixture), { status: 200 });
      }
      if (url.includes('/api/workflows')) {
        return new Response(JSON.stringify(workflowStateFixture), { status: 200 });
      }
      if (url.includes('/api/audit-events')) {
        return new Response(JSON.stringify(auditFixture), { status: 200 });
      }
      if (url.includes('/extraction')) {
        return new Response(JSON.stringify(extractionFixture), { status: 200 });
      }
      if (url.includes('/indexing')) {
        return new Response(JSON.stringify(indexingFixture), { status: 200 });
      }
      if (url.includes('/questions')) {
        return new Response(JSON.stringify(questionsFixture), { status: 200 });
      }
      return new Response(JSON.stringify(documentFixture), { status: 200 });
    });
    vi.stubGlobal('fetch', fetchMock);

    renderWithProviders(<App />, `/documents/${documentFixture.id}`);

    fireEvent.click(await screen.findByRole('button', { name: 'Correct Purchase order number' }));
    fireEvent.change(screen.getByLabelText('Corrected value'), { target: { value: 'PO-2026-001' } });
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Requester supplied it' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('PO-2026-001')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/documents/${documentFixture.id}/fields/${extractionFixture.fields[2]!.id}`,
      expect.objectContaining({ method: 'PATCH' }),
    );
  });
});
