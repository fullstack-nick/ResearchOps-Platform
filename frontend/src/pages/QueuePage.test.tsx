import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../App';
import {
  authConfigFixture,
  currentUserFixture,
  devUsersFixture,
  documentListFixture,
} from '../test/fixtures';
import { renderWithProviders } from '../test/render';

describe('QueuePage', () => {
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
        if (url.includes('/api/auth/dev-users')) {
          return new Response(JSON.stringify(devUsersFixture), { status: 200 });
        }
        return new Response(JSON.stringify(documentListFixture), { status: 200 });
      }),
    );
  });

  it('renders documents in the selected workflow queue', async () => {
    renderWithProviders(<App />, '/queues/procurement');

    expect(await screen.findByText('invoice_helix_lab_supplies.pdf')).toBeInTheDocument();
    expect(screen.getByText('awaiting review')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('1 missing')).toBeInTheDocument();
    expect(screen.getAllByText('Procurement').length).toBeGreaterThan(0);
  });
});
