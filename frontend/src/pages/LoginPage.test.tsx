import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../App';
import {
  authConfigFixture,
  currentUserFixture,
  dashboardFixture,
  devUsersFixture,
} from '../test/fixtures';
import { renderWithProviders } from '../test/render';

describe('LoginPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('lists seeded personas and lets the user switch identity', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes('/api/auth/config')) {
          return new Response(JSON.stringify(authConfigFixture), { status: 200 });
        }
        if (url.includes('/api/auth/dev-users')) {
          return new Response(JSON.stringify(devUsersFixture), { status: 200 });
        }
        if (url.includes('/api/auth/me')) {
          return new Response(JSON.stringify(currentUserFixture), { status: 200 });
        }
        return new Response(JSON.stringify(dashboardFixture), { status: 200 });
      }),
    );

    renderWithProviders(<App />, '/login');

    expect(await screen.findByText('Sign in to ResearchOps')).toBeInTheDocument();
    expect(await screen.findByText('Bob Group Lead')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Alice Researcher/ }));

    await waitFor(() => {
      expect(window.localStorage.getItem('researchops:auth:dev-email')).toBe(
        'researcher.alice@example.test',
      );
    });
  });

  it('renders the Microsoft sign-in CTA when the auth mode is Entra', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes('/api/auth/config')) {
          return new Response(
            JSON.stringify({
              ...authConfigFixture,
              auth_mode: 'entra',
              entra_client_id: 'client-id',
            }),
            { status: 200 },
          );
        }
        if (url.includes('/api/auth/me')) {
          return new Response(JSON.stringify({}), { status: 401 });
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );

    renderWithProviders(<App />, '/login');

    expect(
      await screen.findByText('Sign in with Microsoft Entra ID'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /Sign in with Microsoft/ }),
    ).toBeInTheDocument();
  });
});
