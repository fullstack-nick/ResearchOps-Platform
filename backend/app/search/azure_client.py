from __future__ import annotations

from io import BytesIO
from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchIndex,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery
from fastapi import HTTPException, status
from openai import AzureOpenAI, OpenAIError

from app.core.config import Settings
from app.core.observability import observe_dependency
from app.extraction.azure_client import build_document_intelligence_client

VECTOR_PROFILE_NAME = "researchops-vector-profile"
VECTOR_ALGORITHM_NAME = "researchops-hnsw"
COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"
# Edm type strings are passed literally because azure-search-documents' enum uses a
# case-insensitive metaclass that static type checkers cannot model.
EDM_STRING = "Edm.String"
EDM_INT32 = "Edm.Int32"
EDM_SINGLE_COLLECTION = "Collection(Edm.Single)"


class SearchAzureError(RuntimeError):
    pass


def require_search_settings(settings: Settings) -> None:
    if not settings.azure_search_endpoint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AZURE_SEARCH_ENDPOINT is required for Phase 3 document Q&A.",
        )


def require_openai_settings(settings: Settings) -> None:
    if not settings.azure_openai_endpoint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AZURE_OPENAI_ENDPOINT is required for Phase 3 document Q&A.",
        )


def build_search_index_client(settings: Settings) -> SearchIndexClient:
    require_search_settings(settings)
    endpoint = str(settings.azure_search_endpoint)
    if settings.azure_search_api_key:
        return SearchIndexClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(settings.azure_search_api_key),
        )
    return SearchIndexClient(endpoint=endpoint, credential=DefaultAzureCredential())


def build_search_client(settings: Settings) -> SearchClient:
    require_search_settings(settings)
    endpoint = str(settings.azure_search_endpoint)
    if settings.azure_search_api_key:
        credential: AzureKeyCredential | DefaultAzureCredential = AzureKeyCredential(
            settings.azure_search_api_key
        )
    else:
        credential = DefaultAzureCredential()
    return SearchClient(
        endpoint=endpoint,
        index_name=settings.azure_search_index_name,
        credential=credential,
    )


def build_openai_client(settings: Settings) -> AzureOpenAI:
    require_openai_settings(settings)
    endpoint = str(settings.azure_openai_endpoint)
    if settings.azure_openai_api_key:
        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), COGNITIVE_SERVICES_SCOPE
    )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=settings.azure_openai_api_version,
    )


def ensure_search_index(settings: Settings) -> None:
    client = build_search_index_client(settings)
    fields = [
        SearchField(name="chunk_id", type=EDM_STRING, key=True, filterable=True),
        SearchField(name="document_id", type=EDM_STRING, filterable=True),
        SearchField(name="document_version_id", type=EDM_STRING, filterable=True),
        SearchField(name="workflow_type", type=EDM_STRING, filterable=True),
        SearchField(
            name="chunk_index", type=EDM_INT32, filterable=True, sortable=True
        ),
        SearchField(name="page_number", type=EDM_INT32, filterable=True),
        SearchField(name="content", type=EDM_STRING, searchable=True),
        SearchField(
            name="content_vector",
            type=EDM_SINGLE_COLLECTION,
            searchable=True,
            vector_search_dimensions=settings.azure_openai_embedding_dimensions,
            vector_search_profile_name=VECTOR_PROFILE_NAME,
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name=VECTOR_ALGORITHM_NAME)],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_PROFILE_NAME,
                algorithm_configuration_name=VECTOR_ALGORITHM_NAME,
            )
        ],
    )
    index = SearchIndex(
        name=settings.azure_search_index_name,
        fields=fields,
        vector_search=vector_search,
    )
    try:
        with observe_dependency(
            "azure.search.ensure_index",
            {
                "azure.service": "ai_search",
                "search.index": settings.azure_search_index_name,
            },
        ):
            client.create_or_update_index(index)
    except AzureError as exc:
        raise SearchAzureError("Azure AI Search index creation failed.") from exc


def analyze_document_text(settings: Settings, document_bytes: bytes) -> Any:
    client = build_document_intelligence_client(settings)
    try:
        with observe_dependency(
            "azure.document_intelligence.analyze_read",
            {
                "azure.service": "document_intelligence",
                "azure.model_id": settings.azure_document_intelligence_read_model_id,
                "document.size_bytes": len(document_bytes),
            },
        ):
            poller = client.begin_analyze_document(
                settings.azure_document_intelligence_read_model_id,
                body=BytesIO(document_bytes),
            )
            return poller.result()
    except AzureError as exc:
        raise SearchAzureError(
            "Azure Document Intelligence read analysis failed."
        ) from exc


def embed_texts(settings: Settings, texts: list[str]) -> list[list[float]]:
    client = build_openai_client(settings)
    try:
        with observe_dependency(
            "azure.openai.embeddings",
            {
                "azure.service": "openai",
                "openai.deployment": settings.azure_openai_embedding_deployment,
                "openai.input_count": len(texts),
            },
        ):
            response = client.embeddings.create(
                model=settings.azure_openai_embedding_deployment,
                input=texts,
                dimensions=settings.azure_openai_embedding_dimensions,
            )
    except OpenAIError as exc:
        raise SearchAzureError("Azure OpenAI embedding request failed.") from exc
    return [list(item.embedding) for item in response.data]


def upload_chunk_documents(settings: Settings, documents: list[dict[str, Any]]) -> None:
    if not documents:
        return
    client: Any = build_search_client(settings)
    try:
        with observe_dependency(
            "azure.search.upload_documents",
            {
                "azure.service": "ai_search",
                "search.index": settings.azure_search_index_name,
                "search.document_count": len(documents),
            },
        ):
            client.upload_documents(documents=documents)
    except AzureError as exc:
        raise SearchAzureError("Azure AI Search chunk upload failed.") from exc


def delete_chunks_from_index(settings: Settings, document_id: str) -> None:
    client: Any = build_search_client(settings)
    try:
        with observe_dependency(
            "azure.search.delete_document_chunks",
            {"azure.service": "ai_search", "search.index": settings.azure_search_index_name},
        ):
            existing = client.search(
                search_text="*",
                filter=f"document_id eq '{document_id}'",
                select=["chunk_id"],
                top=1000,
            )
            keys: list[dict[str, Any]] = [
                {"chunk_id": item["chunk_id"]} for item in existing
            ]
            if keys:
                client.delete_documents(documents=keys)
    except AzureError as exc:
        raise SearchAzureError("Azure AI Search chunk cleanup failed.") from exc


def search_document_chunks(
    settings: Settings,
    document_id: str,
    query: str,
    vector: list[float],
    top: int,
) -> list[dict[str, Any]]:
    client: Any = build_search_client(settings)
    vector_query = VectorizedQuery(
        vector=vector,
        k_nearest_neighbors=top,
        fields="content_vector",
    )
    chunks: list[dict[str, Any]] = []
    try:
        with observe_dependency(
            "azure.search.hybrid_query",
            {
                "azure.service": "ai_search",
                "search.index": settings.azure_search_index_name,
                "search.top": top,
            },
        ):
            results = client.search(
                search_text=query,
                vector_queries=[vector_query],
                filter=f"document_id eq '{document_id}'",
                select=["chunk_id", "document_id", "chunk_index", "page_number", "content"],
                top=top,
            )
            for item in results:
                chunks.append(
                    {
                        "chunk_id": item["chunk_id"],
                        "document_id": item["document_id"],
                        "chunk_index": item["chunk_index"],
                        "page_number": item.get("page_number"),
                        "content": item["content"],
                        "score": item.get("@search.score"),
                    }
                )
    except AzureError as exc:
        raise SearchAzureError("Azure AI Search hybrid query failed.") from exc
    return chunks


def generate_grounded_answer(
    settings: Settings,
    question: str,
    chunks: list[dict[str, Any]],
) -> str:
    client = build_openai_client(settings)
    context = "\n\n".join(
        f"[Source {index + 1} | page {chunk.get('page_number') or 'n/a'}]\n{chunk['content']}"
        for index, chunk in enumerate(chunks)
    )
    system_prompt = (
        "You are the ResearchOps document assistant. Answer the question using only the "
        "provided document sources. If the answer is not contained in the sources, say "
        "you cannot find it in this document. Be concise and cite sources as [Source N]."
    )
    user_prompt = f"Document sources:\n{context}\n\nQuestion: {question}"
    try:
        with observe_dependency(
            "azure.openai.chat_completion",
            {
                "azure.service": "openai",
                "openai.deployment": settings.azure_openai_chat_deployment,
                "openai.source_count": len(chunks),
            },
        ):
            response = client.chat.completions.create(
                model=settings.azure_openai_chat_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=600,
            )
    except OpenAIError as exc:
        raise SearchAzureError("Azure OpenAI chat completion failed.") from exc
    return (response.choices[0].message.content or "").strip()
