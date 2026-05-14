import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ExternalLink, FileSearch } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { api } from '../api/client';
import { formatBytes, formatDateTime, workflowLabels } from '../api/labels';
import { PdfPreview } from '../components/PdfPreview';
import { StatusBadge } from '../components/StatusBadge';

export function DocumentPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const documentQuery = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => api.getDocument(documentId!),
    enabled: Boolean(documentId),
  });
  const auditQuery = useQuery({
    queryKey: ['audit-events', documentId],
    queryFn: () => api.getAuditEvents(documentId!),
    enabled: Boolean(documentId),
  });

  if (documentQuery.isLoading) return <p className="text-sm text-slate-600">Loading document workspace...</p>;
  if (documentQuery.error || !documentQuery.data) return <p className="text-sm text-red-700">Document could not be loaded.</p>;

  const document = documentQuery.data;
  const auditEvents = auditQuery.data?.audit_events ?? [];
  const fileUrl = api.documentFileUrl(document.id);

  return (
    <div className="space-y-5">
      <Link to="/queues" className="focus-ring inline-flex items-center gap-2 text-sm font-semibold text-slate-700 hover:text-slate-950">
        <ArrowLeft aria-hidden="true" size={16} />
        Back to queues
      </Link>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">{document.original_filename}</h2>
          <p className="mt-1 text-sm text-slate-600">{workflowLabels[document.workflow_type]} workflow</p>
        </div>
        <StatusBadge status={document.workflow.status} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(360px,0.7fr)]">
        <section className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-base font-semibold text-slate-950">Document preview</h3>
              <a
                href={fileUrl}
                target="_blank"
                rel="noreferrer"
                className="focus-ring inline-flex h-9 items-center gap-2 rounded border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:border-slate-500"
              >
                <ExternalLink aria-hidden="true" size={15} />
                Open PDF
              </a>
            </div>
          </div>
          <PdfPreview fileUrl={fileUrl} />
        </section>

        <div className="space-y-5">
          <section className="rounded border border-slate-200 bg-white p-4">
            <h3 className="text-base font-semibold text-slate-950">Document metadata</h3>
            <dl className="mt-3 grid grid-cols-1 gap-3 text-sm">
              <div>
                <dt className="font-medium text-slate-500">Uploaded</dt>
                <dd className="mt-1 text-slate-900">{formatDateTime(document.created_at)}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Size</dt>
                <dd className="mt-1 text-slate-900">{formatBytes(document.size_bytes)}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">SHA-256</dt>
                <dd className="mt-1 break-all font-mono text-xs text-slate-800">{document.sha256}</dd>
              </div>
            </dl>
          </section>

          <section className="rounded border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2">
              <FileSearch aria-hidden="true" size={18} className="text-slate-500" />
              <h3 className="text-base font-semibold text-slate-950">Extraction and summary</h3>
            </div>
            <p className="mt-3 rounded border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
              Not processed yet. Azure AI Document Intelligence extraction, confidence scores, and source-grounded summaries begin in Phase 2.
            </p>
          </section>

          <section className="rounded border border-slate-200 bg-white p-4">
            <h3 className="text-base font-semibold text-slate-950">Audit timeline</h3>
            {auditQuery.isLoading ? (
              <p className="mt-3 text-sm text-slate-600">Loading audit timeline...</p>
            ) : (
              <ol className="mt-3 space-y-3">
                {auditEvents.map((event) => (
                  <li key={event.event_id} className="border-l-2 border-slate-200 pl-3">
                    <p className="text-sm font-semibold text-slate-900">{event.event_type}</p>
                    <p className="text-xs text-slate-500">{formatDateTime(event.timestamp)} by {event.actor_type}</p>
                    {event.reason && <p className="mt-1 text-sm text-slate-600">{event.reason}</p>}
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
