from app.core.config import Settings
from app.documents.azure_storage import require_azure_storage_settings
from app.extraction.azure_client import (
    DocumentIntelligenceConfigurationError,
    require_document_intelligence_settings,
)
from app.search.azure_client import require_openai_settings, require_search_settings
from fastapi import HTTPException


def test_azure_storage_settings_require_container_and_connection() -> None:
    settings = Settings()

    try:
        require_azure_storage_settings(settings)
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("Missing Azure storage settings should fail.")


def test_document_intelligence_settings_require_endpoint() -> None:
    settings = Settings()

    try:
        require_document_intelligence_settings(settings)
    except DocumentIntelligenceConfigurationError as exc:
        assert "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT" in str(exc)
    else:
        raise AssertionError("Missing Document Intelligence endpoint should fail.")


def test_azure_search_settings_require_endpoint() -> None:
    settings = Settings(azure_search_endpoint=None)

    try:
        require_search_settings(settings)
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("Missing Azure Search endpoint should fail.")


def test_azure_openai_settings_require_endpoint() -> None:
    settings = Settings(azure_openai_endpoint=None)

    try:
        require_openai_settings(settings)
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("Missing Azure OpenAI endpoint should fail.")
