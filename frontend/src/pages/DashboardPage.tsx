import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Clock3, FileText, ListChecks } from 'lucide-react';
import { Link } from 'react-router-dom';

import { api } from '../api/client';
import { workflowLabels } from '../api/labels';
import { EmptyState } from '../components/EmptyState';

const metricItems = [
  { key: 'total_documents', label: 'Documents', icon: FileText },
  { key: 'awaiting_review', label: 'Awaiting review', icon: ListChecks },
  { key: 'recent_failures', label: 'Extraction failures', icon: AlertTriangle },
  { key: 'average_processing_seconds', label: 'Avg processing', icon: Clock3 },
] as const;

export function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: api.getDashboardSummary,
  });

  if (isLoading) return <p className="text-sm text-slate-600">Loading dashboard...</p>;
  if (error) return <p className="text-sm text-red-700">Dashboard data could not be loaded.</p>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">Operations dashboard</h2>
          <p className="mt-1 text-sm text-slate-600">Document intake, workflow review, and audit readiness.</p>
        </div>
        <Link
          to="/upload"
          className="focus-ring inline-flex h-10 items-center justify-center rounded bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-700"
        >
          Upload document
        </Link>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Dashboard metrics">
        {metricItems.map((item) => {
          const value = data[item.key];
          return (
            <div key={item.key} className="rounded border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-slate-600">{item.label}</span>
                <item.icon aria-hidden="true" className="text-slate-500" size={18} />
              </div>
              <p className="mt-3 text-2xl font-semibold text-slate-950">
                {item.key === 'average_processing_seconds' ? 'N/A' : value}
              </p>
            </div>
          );
        })}
      </section>

      {data.total_documents === 0 ? (
        <EmptyState />
      ) : (
        <section className="rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3">
            <h3 className="text-base font-semibold text-slate-950">Workflow queues</h3>
          </div>
          <div className="divide-y divide-slate-100">
            {data.documents_by_workflow.map((queue) => (
              <Link
                key={queue.workflow_type}
                to={`/queues/${queue.workflow_type}`}
                className="focus-ring flex items-center justify-between gap-4 px-4 py-3 hover:bg-slate-50"
              >
                <span className="text-sm font-medium text-slate-800">{workflowLabels[queue.workflow_type]}</span>
                <span className="rounded bg-slate-100 px-2 py-1 text-sm font-semibold text-slate-800">{queue.count}</span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
