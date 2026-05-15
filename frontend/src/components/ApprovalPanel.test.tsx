import { fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkflowState } from '../api/types';
import {
  authConfigFixture,
  currentUserFixture,
  workflowStateFixture,
} from '../test/fixtures';
import { renderWithProviders } from '../test/render';
import { ApprovalPanel } from './ApprovalPanel';

describe('ApprovalPanel', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders all chain steps with statuses and the decide form when allowed', async () => {
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
        return new Response(JSON.stringify(workflowStateFixture), { status: 200 });
      }),
    );

    renderWithProviders(<ApprovalPanel workflowId={workflowStateFixture.id} />);

    expect(await screen.findByText('Approval workflow')).toBeInTheDocument();
    expect(await screen.findByText('intake review')).toBeInTheDocument();
    expect(screen.getByText('group lead approval')).toBeInTheDocument();
    expect(screen.getByText('finance approval')).toBeInTheDocument();
    expect(
      await screen.findByRole('button', { name: 'Approve step' }),
    ).not.toBeDisabled();
    expect(screen.getByRole('button', { name: 'Reject step' })).not.toBeDisabled();
  });

  it('submits an approval decision and refreshes the workflow state', async () => {
    let decided = false;
    const approvedState: WorkflowState = {
      ...workflowStateFixture,
      status: 'awaiting_review',
      current_step: 'group_lead_approval',
      pending_step_id: workflowStateFixture.steps[1]!.id,
      steps: [
        {
          ...workflowStateFixture.steps[0]!,
          status: 'completed',
          completed_at: '2026-05-14T10:05:00Z',
          approvals: [
            {
              id: 'ap-1',
              workflow_id: workflowStateFixture.id,
              workflow_step_id: workflowStateFixture.steps[0]!.id,
              approver_user_id: currentUserFixture.id,
              decision: 'approved',
              reason: 'looks good',
              created_at: '2026-05-14T10:05:00Z',
            },
          ],
        },
        workflowStateFixture.steps[1]!,
        workflowStateFixture.steps[2]!,
      ],
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      if (url.includes('/api/auth/me')) {
        return new Response(JSON.stringify(currentUserFixture), { status: 200 });
      }
      if (url.includes('/api/auth/config')) {
        return new Response(JSON.stringify(authConfigFixture), { status: 200 });
      }
      if (init?.method === 'POST' && url.includes('/decision')) {
        decided = true;
        return new Response(JSON.stringify(approvedState), { status: 200 });
      }
      return new Response(
        JSON.stringify(decided ? approvedState : workflowStateFixture),
        { status: 200 },
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    renderWithProviders(<ApprovalPanel workflowId={workflowStateFixture.id} />);

    fireEvent.change(await screen.findByLabelText('Decision reason'), {
      target: { value: 'looks good' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Approve step' }));

    expect(await screen.findByText(/Approved/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/workflows/${workflowStateFixture.id}/steps/${workflowStateFixture.steps[0]!.id}/decision`,
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('disables decision buttons when the current user cannot decide', async () => {
    const locked: WorkflowState = {
      ...workflowStateFixture,
      can_decide_current_step: false,
    };
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
        return new Response(JSON.stringify(locked), { status: 200 });
      }),
    );

    renderWithProviders(<ApprovalPanel workflowId={workflowStateFixture.id} />);

    expect(await screen.findByRole('button', { name: 'Approve step' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Reject step' })).toBeDisabled();
  });
});
