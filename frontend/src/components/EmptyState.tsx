import { Inbox } from 'lucide-react';
import { Link } from 'react-router-dom';

export function EmptyState() {
  return (
    <div className="rounded border border-dashed border-slate-300 bg-white p-8 text-center">
      <Inbox aria-hidden="true" className="mx-auto mb-3 text-slate-400" size={32} />
      <h2 className="text-base font-semibold text-slate-950">No documents yet</h2>
      <p className="mt-1 text-sm text-slate-600">Upload a synthetic Phase 1 PDF to create the first workflow item.</p>
      <Link
        to="/upload"
        className="focus-ring mt-4 inline-flex h-10 items-center rounded bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-700"
      >
        Upload document
      </Link>
    </div>
  );
}
