import { fireEvent, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from '../App';
import { renderWithProviders } from '../test/render';

describe('UploadPage', () => {
  it('validates that Phase 2 only accepts PDFs', async () => {
    renderWithProviders(<App />, '/upload');

    const input = screen.getByLabelText('PDF document');
    const file = new File(['not a pdf'], 'notes.txt', { type: 'text/plain' });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /upload and create workflow/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Only PDF files can be uploaded');
  });
});
