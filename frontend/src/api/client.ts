import type {
  AuditEventListResponse,
  DashboardSummary,
  DocumentListResponse,
  DocumentRecord,
  ExtractedField,
  ExtractionResponse,
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

  async listDocuments(workflowType?: WorkflowType, status?: string): Promise<DocumentListResponse> {
    const params = new URLSearchParams();
    if (workflowType) params.set('workflow_type', workflowType);
    if (status) params.set('status', status);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request<DocumentListResponse>(`/api/documents${query}`);
  },

  async getDocument(documentId: string): Promise<DocumentRecord> {
    return request<DocumentRecord>(`/api/documents/${documentId}`);
  },

  async getAuditEvents(documentId: string): Promise<AuditEventListResponse> {
    return request<AuditEventListResponse>(`/api/audit-events?document_id=${documentId}`);
  },

  async getDocumentExtraction(documentId: string): Promise<ExtractionResponse> {
    return request<ExtractionResponse>(`/api/documents/${documentId}/extraction`);
  },

  async retryExtraction(documentId: string): Promise<ExtractionResponse> {
    return request<ExtractionResponse>(`/api/documents/${documentId}/extraction/retry`, {
      method: 'POST',
    });
  },

  async correctField(
    documentId: string,
    fieldId: string,
    correctedValue: string,
    reason: string,
  ): Promise<ExtractedField> {
    return request<ExtractedField>(`/api/documents/${documentId}/fields/${fieldId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ corrected_value: correctedValue, reason }),
    });
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
