import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, ShieldQuestion, XCircle } from 'lucide-react';
import { FormEvent, useState } from 'react';

import { api } from '../api/client';
import { formatDateTime } from '../api/labels';
import { useAuth } from '../auth/AuthContext';
import { StatusBadge } from './StatusBadge';

type ApprovalPanelProps = {
  workflowId: string;
};

export function ApprovalPanel({ workflowId }: ApprovalPanelProps) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [reason, setReason] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const workflowQuery = useQuery({
    queryKey: ['workflow-state', workflowId],
    queryFn: () => api.getWorkflowState(workflowId),
  });

  const decisionMutation = useMutation({
    mutationFn: ({ stepId, decision }: { stepId: string; decision: 'approved' | 'rejected' }) =>
      api.decideWorkflowStep(workflowId, stepId, decision, reason.trim() || null),
    onSuccess: async () => {
      setReason('');
      setValidationError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['workflow-state', workflowId] }),
        queryClient.invalidateQueries({ queryKey: ['audit-events'] }),
        queryClient.invalidateQueries({ queryKey: ['documents'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] }),
      ]);
    },
  });

  const rawWorkflow = workflowQuery.data;
  const workflow =
    rawWorkflow && Array.isArray(rawWorkflow.steps) ? rawWorkflow : undefined;
  const pendingStep = workflow?.steps.find((step) => step.id === workflow?.pending_step_id);
  const canDecide = workflow?.can_decide_current_step ?? false;

  function submit(event: FormEvent<HTMLFormElement>, decision: 'approved' | 'rejected') {
    event.preventDefault();
    setValidationError(null);
    if (!pendingStep) return;
    if (decision === 'rejected' && reason.trim().length < 3) {
      setValidationError('A rejection reason of at least 3 characters is required.');
      return;
    }
    decisionMutation.mutate({ stepId: pendingStep.id, decision });
  }

  return (
    <section className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ShieldQuestion aria-hidden="true" size={18} className="text-slate-500" />
          <h3 className="text-base font-semibold text-slate-950">Approval workflow</h3>
        </div>
        {workflow && <StatusBadge status={workflow.status} />}
      </div>

      {workflowQuery.isLoading ? (
        <p className="mt-3 text-sm text-slate-600">Loading workflow state...</p>
      ) : workflowQuery.error || !workflow ? (
        <p
          role="alert"
          className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-800"
        >
          Workflow state could not be loaded.
        </p>
      ) : (
        <div className="mt-4 space-y-4">
          <ol className="space-y-2">
            {workflow.steps.map((step) => {
              const isPending = step.id === workflow.pending_step_id;
              return (
                <li
                  key={step.id}
                  className={`rounded border px-3 py-2 ${
                    isPending
                      ? 'border-blue-200 bg-blue-50'
                      : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-white px-2 py-0.5 text-xs font-semibold text-slate-700">
                        Step {step.step_order + 1}
                      </span>
                      <span className="text-sm font-semibold text-slate-900">
                        {step.step_name.replaceAll('_', ' ')}
                      </span>
                      <span className="text-xs text-slate-500">
                        {step.assigned_role.replaceAll('_', ' ')}
                      </span>
                    </div>
                    <StatusBadge status={step.status} />
                  </div>
                  {step.completed_at && (
                    <p className="mt-1 text-xs text-slate-500">
                      Completed {formatDateTime(step.completed_at)}
                    </p>
                  )}
                  {step.approvals.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {step.approvals.map((approval) => (
                        <li
                          key={approval.id}
                          className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
                        >
                          <span className="font-semibold">
                            {approval.decision === 'approved' ? 'Approved' : 'Rejected'}
                          </span>{' '}
                          · {formatDateTime(approval.created_at)}
                          {approval.reason ? ` · ${approval.reason}` : ''}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ol>

          {workflow.status === 'awaiting_review' && pendingStep && (
            <form
              onSubmit={(event) => submit(event, 'approved')}
              className="space-y-2 rounded border border-slate-200 bg-slate-50 p-3"
            >
              <p className="text-xs text-slate-600">
                {canDecide
                  ? `You can decide '${pendingStep.step_name.replaceAll('_', ' ')}' as ${
                      user?.display_name ?? 'the current user'
                    }.`
                  : `This step requires the '${pendingStep.assigned_role}' role` +
                    (workflow.research_group
                      ? ` for research group '${workflow.research_group}'.`
                      : '.')}
              </p>
              <label className="block">
                <span className="text-xs font-semibold text-slate-600">Decision reason</span>
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  rows={2}
                  placeholder="Optional for approval, required for rejection"
                  disabled={!canDecide}
                  className="focus-ring mt-1 w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 disabled:bg-slate-100 disabled:text-slate-500"
                />
              </label>
              {(validationError || decisionMutation.error) && (
                <p role="alert" className="text-xs text-red-700">
                  {validationError
                    ?? 'The decision could not be submitted. Check your role and try again.'}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <button
                  type="submit"
                  disabled={!canDecide || decisionMutation.isPending}
                  className="focus-ring inline-flex h-9 items-center gap-2 rounded bg-emerald-700 px-3 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-emerald-300"
                >
                  <CheckCircle2 aria-hidden="true" size={15} />
                  Approve step
                </button>
                <button
                  type="button"
                  disabled={!canDecide || decisionMutation.isPending}
                  onClick={(event) => submit(event as unknown as FormEvent<HTMLFormElement>, 'rejected')}
                  className="focus-ring inline-flex h-9 items-center gap-2 rounded border border-red-300 bg-white px-3 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:border-red-200 disabled:text-red-300"
                >
                  <XCircle aria-hidden="true" size={15} />
                  Reject step
                </button>
              </div>
            </form>
          )}

          {workflow.status === 'approved' && (
            <p className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              All approval steps have been completed.
            </p>
          )}
          {workflow.status === 'rejected' && (
            <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              This workflow was rejected.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
