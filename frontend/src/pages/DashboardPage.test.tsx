import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../App';
import {
  authConfigFixture,
  currentUserFixture,
  dashboardFixture,
  devUsersFixture,
} from '../test/fixtures';
import { renderWithProviders } from '../test/render';

describe('DashboardPage', () => {
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
        return new Response(JSON.stringify(dashboardFixture), { status: 200 });
      }),
    );
  });

  it('renders operations metrics and queue links', async () => {
    renderWithProviders(<App />);

    expect(await screen.findByText('Operations dashboard')).toBeInTheDocument();
    expect(screen.getByText('Documents')).toBeInTheDocument();
    expect(screen.getByText('Awaiting review')).toBeInTheDocument();
    expect(screen.getByText('Missing fields')).toBeInTheDocument();
    expect(screen.getByText('Procurement')).toBeInTheDocument();
  });
});
