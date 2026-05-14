import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, MessagesSquare, RefreshCw, Send } from 'lucide-react';
import { FormEvent, useState } from 'react';

import { api } from '../api/client';
import { formatDateTime } from '../api/labels';
import type { QuestionAnswer } from '../api/types';
import { StatusBadge } from './StatusBadge';

export function QaPanel({ documentId }: { documentId: string }) {
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const indexingQuery = useQuery({
    queryKey: ['document-indexing', documentId],
    queryFn: () => api.getDocumentIndexing(documentId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'pending' || status === 'processing' ? 2000 : false;
    },
  });
  const questionsQuery = useQuery({
    queryKey: ['document-questions', documentId],
    queryFn: () => api.getQuestions(documentId),
  });

  const retryMutation = useMutation({
    mutationFn: () => api.retryIndexing(documentId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['document-indexing', documentId] });
    },
  });
  const askMutation = useMutation({
    mutationFn: (value: string) => api.askQuestion(documentId, value),
    onSuccess: async () => {
      setQuestion('');
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['document-questions', documentId] }),
        queryClient.invalidateQueries({ queryKey: ['audit-events', documentId] }),
      ]);
    },
  });

  const indexing = indexingQuery.data;
  const questions = questionsQuery.data?.questions ?? [];

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationError(null);
    const trimmed = question.trim();
    if (trimmed.length < 3) {
      setValidationError('Enter a question of at least 3 characters.');
      return;
    }
    askMutation.mutate(trimmed);
  }

  return (
    <section className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MessagesSquare aria-hidden="true" size={18} className="text-slate-500" />
          <h3 className="text-base font-semibold text-slate-950">Document Q&amp;A</h3>
        </div>
        {indexing && <StatusBadge status={indexing.status} />}
      </div>

      {indexingQuery.isLoading ? (
        <p className="mt-3 text-sm text-slate-600">Loading indexing status...</p>
      ) : !indexing || indexing.status === 'not_requested' ? (
        <p className="mt-3 rounded border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
          Document Q&amp;A indexing has not been requested for this document.
        </p>
      ) : indexing.status === 'pending' || indexing.status === 'processing' ? (
        <p className="mt-3 rounded border border-blue-200 bg-blue-50 px-3 py-3 text-sm text-blue-800">
          Azure AI Search indexing is {indexing.status.replaceAll('_', ' ')}. Q&amp;A becomes
          available once the document is indexed.
        </p>
      ) : indexing.status === 'failed' ? (
        <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-800">
          <div className="flex items-start gap-2">
            <AlertTriangle aria-hidden="true" size={17} className="mt-0.5 shrink-0" />
            <p>{indexing.latest_run?.error_message ?? 'Indexing failed.'}</p>
          </div>
          <button
            type="button"
            onClick={() => retryMutation.mutate()}
            disabled={retryMutation.isPending}
            className="focus-ring mt-3 inline-flex h-9 items-center gap-2 rounded bg-red-700 px-3 text-sm font-semibold text-white hover:bg-red-800 disabled:bg-red-300"
          >
            <RefreshCw aria-hidden="true" size={15} />
            {retryMutation.isPending ? 'Retrying...' : 'Retry indexing'}
          </button>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <p className="text-xs text-slate-500">
            {`${indexing.chunk_count} searchable ${
              indexing.chunk_count === 1 ? 'chunk' : 'chunks'
            } indexed in Azure AI Search. Answers are grounded in retrieved document content.`}
          </p>

          <form onSubmit={submit} className="space-y-2">
            <label className="block">
              <span className="text-xs font-semibold text-slate-600">
                Ask about this document
              </span>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                rows={2}
                placeholder="e.g. What is the invoice total and when is it due?"
                className="focus-ring mt-1 w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              />
            </label>
            {(validationError || askMutation.error) && (
              <p role="alert" className="text-xs text-red-700">
                {validationError ?? 'The question could not be answered. Try again.'}
              </p>
            )}
            <button
              type="submit"
              disabled={askMutation.isPending}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-700 disabled:bg-slate-400"
            >
              <Send aria-hidden="true" size={15} />
              {askMutation.isPending ? 'Asking...' : 'Ask question'}
            </button>
          </form>

          <div>
            <h4 className="text-sm font-semibold text-slate-950">Conversation</h4>
            {questionsQuery.isLoading ? (
              <p className="mt-2 text-sm text-slate-600">Loading conversation...</p>
            ) : questions.length === 0 ? (
              <p className="mt-2 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                No questions asked yet. Ask a question to get a source-grounded answer.
              </p>
            ) : (
              <ol className="mt-2 space-y-3">
                {questions.map((entry) => (
                  <QaEntry key={entry.id} entry={entry} />
                ))}
              </ol>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function QaEntry({ entry }: { entry: QuestionAnswer }) {
  return (
    <li className="rounded border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm font-semibold text-slate-900">{entry.question}</p>
      <p className="mt-1 text-xs text-slate-500">{formatDateTime(entry.created_at)}</p>
      {entry.status === 'failed' ? (
        <p className="mt-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {entry.error_message ?? 'This question could not be answered.'}
        </p>
      ) : (
        <>
          <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{entry.answer}</p>
          {entry.citations.length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-semibold text-slate-600">Sources</p>
              <ul className="mt-1 space-y-1">
                {entry.citations.map((citation, index) => (
                  <li
                    key={citation.chunk_id}
                    className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600"
                  >
                    <span className="font-semibold text-slate-700">
                      {`Source ${index + 1}${
                        citation.page_number ? ` · page ${citation.page_number}` : ''
                      }`}
                    </span>
                    <span className="ml-1">{citation.content.slice(0, 200)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </li>
  );
}
