import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../App';
import { dashboardFixture } from '../test/fixtures';
import { renderWithProviders } from '../test/render';

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify(dashboardFixture), { status: 200 })),
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
