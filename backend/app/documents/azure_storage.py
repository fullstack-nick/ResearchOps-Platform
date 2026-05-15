from __future__ import annotations

from dataclasses import dataclass

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from fastapi import HTTPException, status

from app.core.config import Settings
from app.core.observability import observe_dependency


@dataclass(frozen=True)
class BlobUploadResult:
    container: str
    object_key: str
    url: str | None
    etag: str | None


def require_azure_storage_settings(settings: Settings) -> None:
    if not settings.azure_storage_container:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AZURE_STORAGE_CONTAINER is required for Phase 2 uploads.",
        )
    if not settings.azure_storage_connection_string and not settings.azure_storage_account_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Configure AZURE_STORAGE_CONNECTION_STRING or "
                "AZURE_STORAGE_ACCOUNT_URL for Phase 2 uploads."
            ),
        )


def _blob_service_client(settings: Settings) -> BlobServiceClient:
    require_azure_storage_settings(settings)
    if settings.azure_storage_connection_string:
        return BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
    credential = DefaultAzureCredential()
    return BlobServiceClient(
        account_url=str(settings.azure_storage_account_url),
        credential=credential,
    )


def upload_document_blob(
    settings: Settings,
    object_key: str,
    content: bytes,
    content_type: str,
    metadata: dict[str, str],
) -> BlobUploadResult:
    client = _blob_service_client(settings)
    container = settings.azure_storage_container
    if container is None:
        raise AssertionError("Azure storage settings were validated without a container.")
    blob_client = client.get_blob_client(container=container, blob=object_key)
    try:
        with observe_dependency(
            "azure.blob.upload",
            {
                "azure.service": "blob",
                "blob.container": container,
                "blob.content_type": content_type,
                "blob.size_bytes": len(content),
            },
        ):
            result = blob_client.upload_blob(
                content,
                overwrite=False,
                content_settings=ContentSettings(content_type=content_type),
                metadata=metadata,
            )
    except AzureError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Azure Blob upload failed.",
        ) from exc
    return BlobUploadResult(
        container=container,
        object_key=object_key,
        url=blob_client.url,
        etag=getattr(result, "etag", None),
    )


def download_document_blob(settings: Settings, container: str, object_key: str) -> bytes:
    client = _blob_service_client(settings)
    blob_client = client.get_blob_client(container=container, blob=object_key)
    try:
        with observe_dependency(
            "azure.blob.download",
            {"azure.service": "blob", "blob.container": container},
        ):
            return bytes(blob_client.download_blob().readall())
    except AzureError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored Azure Blob document was not found.",
        ) from exc
