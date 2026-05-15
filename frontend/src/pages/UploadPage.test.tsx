import { fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../App';
import { authConfigFixture, currentUserFixture } from '../test/fixtures';
import { renderWithProviders } from '../test/render';

describe('UploadPage', () => {
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
        return new Response('{}', { status: 200 });
      }),
    );
  });

  it('validates that Phase 2 only accepts PDFs', async () => {
    renderWithProviders(<App />, '/upload');

    const input = screen.getByLabelText('PDF document');
    const file = new File(['not a pdf'], 'notes.txt', { type: 'text/plain' });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /upload and create workflow/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Only PDF files can be uploaded');
  });
});
