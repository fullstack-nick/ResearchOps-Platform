import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  FileSearch,
  Pencil,
  RefreshCw,
  Save,
  X,
} from 'lucide-react';
import { FormEvent, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { api } from '../api/client';
import {
  formatAmount,
  formatBytes,
  formatConfidence,
  formatDateTime,
  workflowLabels,
} from '../api/labels';
import type { ExtractedField, ExtractionResponse } from '../api/types';
import { ApprovalPanel } from '../components/ApprovalPanel';
import { PdfPreview } from '../components/PdfPreview';
import { QaPanel } from '../components/QaPanel';
import { StatusBadge } from '../components/StatusBadge';

type CorrectionPayload = {
  fieldId: string;
  correctedValue: string;
  reason: string;
};

export function DocumentPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const queryClient = useQueryClient();
  const documentQuery = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => api.getDocument(documentId!),
    enabled: Boolean(documentId),
  });
  const extractionQuery = useQuery({
    queryKey: ['document-extraction', documentId],
    queryFn: () => api.getDocumentExtraction(documentId!),
    enabled: Boolean(documentId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'pending' || status === 'processing' ? 2000 : false;
    },
  });
  const auditQuery = useQuery({
    queryKey: ['audit-events', documentId],
    queryFn: () => api.getAuditEvents(documentId!),
    enabled: Boolean(documentId),
  });

  const retryMutation = useMutation({
    mutationFn: () => api.retryExtraction(documentId!),
    onSuccess: async () => {
      await invalidateDocumentQueries(queryClient, documentId);
    },
  });
  const correctionMutation = useMutation({
    mutationFn: ({ fieldId, correctedValue, reason }: CorrectionPayload) =>
      api.correctField(documentId!, fieldId, correctedValue, reason),
    onSuccess: async (updatedField) => {
      queryClient.setQueryData<ExtractionResponse>(
        ['document-extraction', documentId],
        (current) =>
          current
            ? {
                ...current,
                fields: current.fields.map((field) =>
                  field.id === updatedField.id ? updatedField : field,
                ),
                missing_fields: current.missing_fields.filter(
                  (fieldKey) => fieldKey !== updatedField.field_key,
                ),
              }
            : current,
      );
      await invalidateDocumentSideQueries(queryClient, documentId);
    },
  });

  if (documentQuery.isLoading) {
    return <p className="text-sm text-slate-600">Loading document workspace...</p>;
  }
  if (documentQuery.error || !documentQuery.data) {
    return <p className="text-sm text-red-700">Document could not be loaded.</p>;
  }

  const document = documentQuery.data;
  const extraction = extractionQuery.data;
  const auditEvents = auditQuery.data?.audit_events ?? [];
  const fileUrl = api.documentFileUrl(document.id);

  return (
    <div className="space-y-5">
      <Link
        to="/queues"
        className="focus-ring inline-flex items-center gap-2 text-sm font-semibold text-slate-700 hover:text-slate-950"
      >
        <ArrowLeft aria-hidden="true" size={16} />
        Back to queues
      </Link>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">{document.original_filename}</h2>
          <p className="mt-1 text-sm text-slate-600">
            {workflowLabels[document.workflow_type]} workflow
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={document.workflow.status} />
          <StatusBadge status={document.status} />
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.25fr)_minmax(390px,0.75fr)]">
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
                <dt className="font-medium text-slate-500">Storage</dt>
                <dd className="mt-1 text-slate-900">
                  {document.versions.at(-1)?.storage_provider.replaceAll('_', ' ') ?? 'unknown'}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">SHA-256</dt>
                <dd className="mt-1 break-all font-mono text-xs text-slate-800">
                  {document.sha256}
                </dd>
              </div>
            </dl>
          </section>

          <ExtractionPanel
            extraction={extraction}
            isLoading={extractionQuery.isLoading}
            isRetrying={retryMutation.isPending}
            retryError={retryMutation.error}
            savingFieldId={correctionMutation.variables?.fieldId ?? null}
            onRetry={() => retryMutation.mutate()}
            onCorrect={(payload) => correctionMutation.mutate(payload)}
          />

          <ApprovalPanel workflowId={document.workflow.id} />

          <QaPanel documentId={document.id} />

          <section className="rounded border border-slate-200 bg-white p-4">
            <h3 className="text-base font-semibold text-slate-950">Audit timeline</h3>
            {auditQuery.isLoading ? (
              <p className="mt-3 text-sm text-slate-600">Loading audit timeline...</p>
            ) : (
              <ol className="mt-3 space-y-3">
                {auditEvents.map((event) => (
                  <li key={event.event_id} className="border-l-2 border-slate-200 pl-3">
                    <p className="text-sm font-semibold text-slate-900">{event.event_type}</p>
                    <p className="text-xs text-slate-500">
                      {formatDateTime(event.timestamp)} by {event.actor_type}
                    </p>
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

function ExtractionPanel({
  extraction,
  isLoading,
  isRetrying,
  retryError,
  savingFieldId,
  onRetry,
  onCorrect,
}: {
  extraction: ExtractionResponse | undefined;
  isLoading: boolean;
  isRetrying: boolean;
  retryError: Error | null;
  savingFieldId: string | null;
  onRetry: () => void;
  onCorrect: (payload: CorrectionPayload) => void;
}) {
  if (isLoading) {
    return (
      <section className="rounded border border-slate-200 bg-white p-4">
        <p className="text-sm text-slate-600">Loading extraction...</p>
      </section>
    );
  }
  if (!extraction || !extraction.available) {
    return (
      <section className="rounded border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2">
          <FileSearch aria-hidden="true" size={18} className="text-slate-500" />
          <h3 className="text-base font-semibold text-slate-950">Extraction</h3>
        </div>
        <p className="mt-3 rounded border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
          Extraction is not available for this workflow type in Phase 2.
        </p>
      </section>
    );
  }

  const isRunning = extraction.status === 'pending' || extraction.status === 'processing';
  const failed = extraction.status === 'failed';
  const fieldLabels = new Map(extraction.fields.map((field) => [field.field_key, field.label]));

  return (
    <section className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileSearch aria-hidden="true" size={18} className="text-slate-500" />
          <h3 className="text-base font-semibold text-slate-950">Invoice extraction</h3>
        </div>
        <StatusBadge status={extraction.status} />
      </div>

      {isRunning && (
        <p className="mt-3 rounded border border-blue-200 bg-blue-50 px-3 py-3 text-sm text-blue-800">
          Azure Document Intelligence extraction is {extraction.status.replaceAll('_', ' ')}.
        </p>
      )}

      {failed && (
        <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-800">
          <div className="flex items-start gap-2">
            <AlertTriangle aria-hidden="true" size={17} className="mt-0.5 shrink-0" />
            <p>{extraction.latest_run?.error_message ?? 'Extraction failed.'}</p>
          </div>
          <button
            type="button"
            onClick={onRetry}
            disabled={isRetrying}
            className="focus-ring mt-3 inline-flex h-9 items-center gap-2 rounded bg-red-700 px-3 text-sm font-semibold text-white hover:bg-red-800 disabled:bg-red-300"
          >
            <RefreshCw aria-hidden="true" size={15} />
            {isRetrying ? 'Retrying...' : 'Retry extraction'}
          </button>
        </div>
      )}

      {retryError && (
        <p role="alert" className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          Retry failed.
        </p>
      )}

      {extraction.status === 'completed' && (
        <div className="mt-4 space-y-4">
          <div>
            <div className="flex items-center gap-2">
              <CheckCircle2 aria-hidden="true" size={17} className="text-emerald-600" />
              <h4 className="text-sm font-semibold text-slate-950">Extracted fields</h4>
            </div>
            <div className="mt-3 divide-y divide-slate-100 rounded border border-slate-200">
              {extraction.fields.map((field) => (
                <ExtractedFieldRow
                  key={field.id}
                  field={field}
                  isSaving={savingFieldId === field.id}
                  onCorrect={(correctedValue, reason) =>
                    onCorrect({ fieldId: field.id, correctedValue, reason })
                  }
                />
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-slate-950">Missing-field checklist</h4>
            {extraction.missing_fields.length === 0 ? (
              <p className="mt-2 rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                No required invoice fields are missing.
              </p>
            ) : (
              <ul className="mt-2 space-y-2">
                {extraction.missing_fields.map((fieldKey) => (
                  <li
                    key={fieldKey}
                    className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900"
                  >
                    {fieldLabels.get(fieldKey) ?? fieldKey.replaceAll('_', ' ')}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h4 className="text-sm font-semibold text-slate-950">Line items</h4>
            <div className="mt-2 overflow-x-auto rounded border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">Description</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Qty</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Unit</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Amount</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {extraction.line_items.map((item) => (
                    <tr key={item.id}>
                      <td className="px-3 py-2 text-slate-900">
                        {item.description ?? 'N/A'}
                      </td>
                      <td className="px-3 py-2 text-right text-slate-700">
                        {item.quantity ?? 'N/A'}
                      </td>
                      <td className="px-3 py-2 text-right text-slate-700">
                        {formatAmount(item.unit_price, item.currency)}
                      </td>
                      <td className="px-3 py-2 text-right text-slate-900">
                        {formatAmount(item.amount, item.currency)}
                      </td>
                      <td className="px-3 py-2 text-right text-slate-700">
                        {formatConfidence(item.confidence)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function ExtractedFieldRow({
  field,
  isSaving,
  onCorrect,
}: {
  field: ExtractedField;
  isSaving: boolean;
  onCorrect: (correctedValue: string, reason: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [correctedValue, setCorrectedValue] = useState(field.display_value ?? '');
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!correctedValue.trim()) {
      setError('Enter a corrected value.');
      return;
    }
    if (reason.trim().length < 3) {
      setError('Enter a correction reason.');
      return;
    }
    onCorrect(correctedValue.trim(), reason.trim());
    setEditing(false);
  }

  return (
    <div className="px-3 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-900">{field.label}</p>
          <p className={field.is_missing ? 'mt-1 text-sm text-amber-800' : 'mt-1 text-sm text-slate-700'}>
            {field.display_value ?? 'Missing'}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Confidence {formatConfidence(field.confidence)}
            {field.source_page ? ` · page ${field.source_page}` : ''}
            {field.corrected_at ? ' · corrected' : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setEditing(true);
            setCorrectedValue(field.display_value ?? '');
          }}
          className="focus-ring inline-flex h-8 w-8 shrink-0 items-center justify-center rounded border border-slate-300 bg-white text-slate-700 hover:border-slate-500"
          title={`Correct ${field.label}`}
          aria-label={`Correct ${field.label}`}
        >
          <Pencil aria-hidden="true" size={15} />
        </button>
      </div>

      {editing && (
        <form onSubmit={submit} className="mt-3 space-y-2 rounded border border-slate-200 bg-slate-50 p-3">
          <label className="block">
            <span className="text-xs font-semibold text-slate-600">Corrected value</span>
            <input
              value={correctedValue}
              onChange={(event) => setCorrectedValue(event.target.value)}
              className="focus-ring mt-1 h-9 w-full rounded border border-slate-300 bg-white px-3 text-sm text-slate-900"
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold text-slate-600">Reason</span>
            <input
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className="focus-ring mt-1 h-9 w-full rounded border border-slate-300 bg-white px-3 text-sm text-slate-900"
            />
          </label>
          {error && <p className="text-xs text-red-700">{error}</p>}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={isSaving}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-700 disabled:bg-slate-400"
            >
              <Save aria-hidden="true" size={15} />
              {isSaving ? 'Saving...' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:border-slate-500"
            >
              <X aria-hidden="true" size={15} />
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

async function invalidateDocumentQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  documentId: string | undefined,
) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['document', documentId] }),
    queryClient.invalidateQueries({ queryKey: ['document-extraction', documentId] }),
    queryClient.invalidateQueries({ queryKey: ['audit-events', documentId] }),
    queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] }),
    queryClient.invalidateQueries({ queryKey: ['documents'] }),
  ]);
}

async function invalidateDocumentSideQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  documentId: string | undefined,
) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['document', documentId] }),
    queryClient.invalidateQueries({ queryKey: ['audit-events', documentId] }),
    queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] }),
    queryClient.invalidateQueries({ queryKey: ['documents'] }),
  ]);
}
