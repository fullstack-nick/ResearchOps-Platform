import { fireEvent, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { documentFixture, indexingFixture, questionsFixture } from '../test/fixtures';
import { renderWithProviders } from '../test/render';
import { QaPanel } from './QaPanel';

describe('QaPanel', () => {
  it('renders indexing status, chunk count, and grounded answers with citations', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes('/questions')) {
          return new Response(JSON.stringify(questionsFixture), { status: 200 });
        }
        return new Response(JSON.stringify(indexingFixture), { status: 200 });
      }),
    );

    renderWithProviders(<QaPanel documentId={documentFixture.id} />);

    expect(await screen.findByText('Document Q&A')).toBeInTheDocument();
    expect(await screen.findByText(/2 searchable chunks indexed/)).toBeInTheDocument();
    expect(await screen.findByText('What is the invoice total?')).toBeInTheDocument();
    expect(screen.getByText('Based on [Source 1]: the invoice total is 4010.30 EUR.')).toBeInTheDocument();
    expect(screen.getByText(/Source 1 · page 1/)).toBeInTheDocument();
  });

  it('submits a question and shows the grounded answer', async () => {
    const newQuestion = {
      id: 'dd000000-0000-4000-8000-000000000009',
      document_id: documentFixture.id,
      question: 'When is payment due?',
      answer: 'Based on [Source 1]: Payment terms are net 14 days from the invoice issue date.',
      status: 'completed',
      citations: [
        {
          chunk_id: `${documentFixture.id}_1`,
          page_number: 2,
          content: 'Payment terms are net 14 days from the invoice issue date.',
          score: 0.9,
        },
      ],
      model_id: 'gpt-4o-mini',
      error_message: null,
      created_at: '2026-05-14T10:10:00Z',
    };
    let asked = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === 'POST' && url.includes('/questions')) {
        asked = true;
        return new Response(JSON.stringify(newQuestion), { status: 201 });
      }
      if (url.includes('/questions')) {
        return new Response(
          JSON.stringify({
            questions: asked
              ? [newQuestion, ...questionsFixture.questions]
              : questionsFixture.questions,
          }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify(indexingFixture), { status: 200 });
    });
    vi.stubGlobal('fetch', fetchMock);

    renderWithProviders(<QaPanel documentId={documentFixture.id} />);

    fireEvent.change(await screen.findByLabelText('Ask about this document'), {
      target: { value: 'When is payment due?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Ask question' }));

    expect(await screen.findByText('When is payment due?')).toBeInTheDocument();
    expect(
      await screen.findByText(/Based on \[Source 1\]: Payment terms are net 14 days/),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/documents/${documentFixture.id}/questions`,
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('shows a retry action when indexing failed', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes('/questions')) {
          return new Response(JSON.stringify({ questions: [] }), { status: 200 });
        }
        return new Response(
          JSON.stringify({
            document_id: documentFixture.id,
            status: 'failed',
            latest_run: {
              ...indexingFixture.latest_run,
              status: 'failed',
              error_message: 'Read model unavailable.',
            },
            chunk_count: 0,
            chunks: [],
          }),
          { status: 200 },
        );
      }),
    );

    renderWithProviders(<QaPanel documentId={documentFixture.id} />);

    expect(await screen.findByText('Read model unavailable.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry indexing' })).toBeInTheDocument();
  });
});
