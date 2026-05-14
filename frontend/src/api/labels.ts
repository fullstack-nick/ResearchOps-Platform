import type { WorkflowType } from './types';

export const workflowLabels: Record<WorkflowType, string> = {
  procurement: 'Procurement',
  hr_onboarding: 'HR onboarding',
  grants: 'Grant administration',
  contracts: 'Contracts',
  reports: 'Reports and minutes',
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function formatConfidence(value: number | null): string {
  if (value === null) return 'N/A';
  return `${Math.round(value * 100)}%`;
}

export function formatAmount(value: number | null, currency: string | null): string {
  if (value === null) return 'N/A';
  if (!currency) return value.toFixed(2);
  return `${currency} ${value.toFixed(2)}`;
}
