import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';

import { api } from '../api/client';
import { formatBytes, formatDateTime, workflowLabels } from '../api/labels';
import { WorkflowType, workflowTypes } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { StatusBadge } from '../components/StatusBadge';

function asWorkflowType(value: string | undefined): WorkflowType | undefined {
  if (!value) return undefined;
  return workflowTypes.includes(value as WorkflowType) ? (value as WorkflowType) : undefined;
}

export function QueuePage() {
  const params = useParams();
  const workflowType = asWorkflowType(params.workflowType);
  const { data, isLoading, error } = useQuery({
    queryKey: ['documents', workflowType ?? 'all'],
    queryFn: () => api.listDocuments(workflowType),
  });

  if (isLoading) return <p className="text-sm text-slate-600">Loading queue...</p>;
  if (error) return <p className="text-sm text-red-700">Workflow queue could not be loaded.</p>;

  const documents = data?.documents ?? [];

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-slate-950">
          {workflowType ? workflowLabels[workflowType] : 'All workflow queues'}
        </h2>
        <p className="mt-1 text-sm text-slate-600">Review local intake items awaiting operational processing.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Link
          to="/queues"
          className="focus-ring rounded border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-slate-400"
        >
          All
        </Link>
        {workflowTypes.map((type) => (
          <Link
            key={type}
            to={`/queues/${type}`}
            className="focus-ring rounded border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-slate-400"
          >
            {workflowLabels[type]}
          </Link>
        ))}
      </div>

      {documents.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">Document</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">Workflow</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">Size</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">Uploaded</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {documents.map((document) => (
                <tr key={document.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link to={`/documents/${document.id}`} className="focus-ring text-sm font-semibold text-blue-700 hover:text-blue-900">
                      {document.original_filename}
                    </Link>
                    <p className="mt-1 max-w-xs truncate text-xs text-slate-500">{document.sha256}</p>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">{workflowLabels[document.workflow_type]}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={document.workflow.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">{formatBytes(document.size_bytes)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{formatDateTime(document.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
