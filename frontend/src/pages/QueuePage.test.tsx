import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../App';
import { documentListFixture } from '../test/fixtures';
import { renderWithProviders } from '../test/render';

describe('QueuePage', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify(documentListFixture), { status: 200 })),
    );
  });

  it('renders documents in the selected workflow queue', async () => {
    renderWithProviders(<App />, '/queues/procurement');

    expect(await screen.findByText('invoice_helix_lab_supplies.pdf')).toBeInTheDocument();
    expect(screen.getByText('awaiting review')).toBeInTheDocument();
    expect(screen.getAllByText('Procurement').length).toBeGreaterThan(0);
  });
});
