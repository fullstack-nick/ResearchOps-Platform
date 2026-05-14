import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FileUp } from 'lucide-react';
import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { workflowLabels } from '../api/labels';
import { WorkflowType, workflowTypes } from '../api/types';

export function UploadPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [workflowType, setWorkflowType] = useState<WorkflowType>('procurement');
  const [file, setFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Select a PDF file before uploading.');
      return api.uploadDocument(file, workflowType);
    },
    onSuccess: async (response) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] }),
        queryClient.invalidateQueries({ queryKey: ['documents'] }),
      ]);
      navigate(`/documents/${response.document.id}`);
    },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationError(null);
    if (!file) {
      setValidationError('Select a PDF file.');
      return;
    }
    if (file.type !== 'application/pdf' || !file.name.toLowerCase().endsWith('.pdf')) {
      setValidationError('Only PDF files can be uploaded in Phase 2.');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setValidationError('PDF uploads must be at most 20 MB.');
      return;
    }
    uploadMutation.mutate();
  }

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold text-slate-950">Upload operational document</h2>
      <p className="mt-1 text-sm text-slate-600">
        Azure-backed intake creates a document record, workflow item, audit trail, and procurement extraction job.
      </p>

      <form onSubmit={onSubmit} className="mt-6 space-y-5 rounded border border-slate-200 bg-white p-5">
        <label className="block">
          <span className="text-sm font-semibold text-slate-800">Workflow type</span>
          <select
            value={workflowType}
            onChange={(event) => setWorkflowType(event.target.value as WorkflowType)}
            className="focus-ring mt-2 h-11 w-full rounded border border-slate-300 bg-white px-3 text-sm text-slate-900"
          >
            {workflowTypes.map((type) => (
              <option key={type} value={type}>
                {workflowLabels[type]}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-semibold text-slate-800">PDF document</span>
          <input
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => setFile(event.currentTarget.files?.[0] ?? null)}
            className="focus-ring mt-2 block w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 file:mr-4 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-slate-800"
          />
        </label>

        {(validationError || uploadMutation.error) && (
          <p role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {validationError ?? 'Upload failed. Check that the backend is running and the file is valid.'}
          </p>
        )}

        <button
          type="submit"
          disabled={uploadMutation.isPending}
          className="focus-ring inline-flex h-11 items-center gap-2 rounded bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          <FileUp aria-hidden="true" size={16} />
          {uploadMutation.isPending ? 'Uploading...' : 'Upload and create workflow'}
        </button>
      </form>
    </div>
  );
}
