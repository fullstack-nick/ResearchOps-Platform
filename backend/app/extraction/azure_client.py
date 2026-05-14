from __future__ import annotations

from io import BytesIO
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential

from app.core.config import Settings


class DocumentIntelligenceConfigurationError(RuntimeError):
    pass


class DocumentIntelligenceAnalyzeError(RuntimeError):
    pass


def require_document_intelligence_settings(settings: Settings) -> None:
    if not settings.azure_document_intelligence_endpoint:
        raise DocumentIntelligenceConfigurationError(
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is required for extraction."
        )


def build_document_intelligence_client(settings: Settings) -> DocumentIntelligenceClient:
    require_document_intelligence_settings(settings)
    endpoint = str(settings.azure_document_intelligence_endpoint)
    if settings.azure_document_intelligence_key:
        credential = AzureKeyCredential(settings.azure_document_intelligence_key)
    else:
        credential = DefaultAzureCredential()
    return DocumentIntelligenceClient(endpoint=endpoint, credential=credential)


def analyze_invoice_document(settings: Settings, document_bytes: bytes) -> Any:
    client = build_document_intelligence_client(settings)
    try:
        poller = client.begin_analyze_document(
            settings.azure_document_intelligence_model_id,
            body=BytesIO(document_bytes),
        )
        return poller.result()
    except AzureError as exc:
        raise DocumentIntelligenceAnalyzeError(
            "Azure Document Intelligence analysis failed."
        ) from exc
