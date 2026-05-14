type StatusBadgeProps = {
  status: string;
};

const styles: Record<string, string> = {
  awaiting_review: 'border-amber-200 bg-amber-50 text-amber-800',
  uploaded: 'border-blue-200 bg-blue-50 text-blue-800',
  approved: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  rejected: 'border-red-200 bg-red-50 text-red-800',
  failed: 'border-red-200 bg-red-50 text-red-800',
  pending: 'border-violet-200 bg-violet-50 text-violet-800',
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const label = status.replaceAll('_', ' ');
  return (
    <span className={`inline-flex rounded border px-2 py-1 text-xs font-semibold ${styles[status] ?? 'border-slate-200 bg-white text-slate-700'}`}>
      {label}
    </span>
  );
}
