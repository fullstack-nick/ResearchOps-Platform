import type {
  AuditEventListResponse,
  DashboardSummary,
  DocumentListResponse,
  DocumentRecord,
  UploadResponse,
  WorkflowType,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  async getDashboardSummary(): Promise<DashboardSummary> {
    return request<DashboardSummary>('/api/dashboard/summary');
  },

  async listDocuments(workflowType?: WorkflowType): Promise<DocumentListResponse> {
    const query = workflowType ? `?workflow_type=${encodeURIComponent(workflowType)}` : '';
    return request<DocumentListResponse>(`/api/documents${query}`);
  },

  async getDocument(documentId: string): Promise<DocumentRecord> {
    return request<DocumentRecord>(`/api/documents/${documentId}`);
  },

  async getAuditEvents(documentId: string): Promise<AuditEventListResponse> {
    return request<AuditEventListResponse>(`/api/audit-events?document_id=${documentId}`);
  },

  async uploadDocument(file: File, workflowType: WorkflowType): Promise<UploadResponse> {
    const form = new FormData();
    form.append('file', file);
    return request<UploadResponse>(`/api/documents?workflow_type=${workflowType}`, {
      method: 'POST',
      body: form,
    });
  },

  documentFileUrl(documentId: string): string {
    return `${API_BASE_URL}/api/documents/${documentId}/file`;
  },
};
