from __future__ import annotations

from typing import Any

import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError, PyJWKClient

from app.core.config import Settings


class EntraConfigurationError(RuntimeError):
    pass


def require_entra_settings(settings: Settings) -> None:
    if not settings.entra_tenant_id or not settings.entra_client_id:
        raise EntraConfigurationError(
            "AUTH_MODE=entra requires ENTRA_TENANT_ID and ENTRA_CLIENT_ID."
        )


def _build_jwks_client(settings: Settings) -> PyJWKClient:
    if not settings.entra_jwks_uri:
        raise EntraConfigurationError(
            "AUTH_MODE=entra requires ENTRA_TENANT_ID to derive the JWKS URI."
        )
    return PyJWKClient(settings.entra_jwks_uri, cache_keys=True, lifespan=3600)


def validate_entra_token(settings: Settings, token: str) -> dict[str, Any]:
    require_entra_settings(settings)
    jwks_client = _build_jwks_client(settings)
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.entra_audience or settings.entra_client_id,
            issuer=settings.entra_issuer,
            options={"require": ["exp", "iss", "aud"]},
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Entra ID token: {exc}",
        ) from exc
    scope_value = decoded.get("scp") or decoded.get("scope") or ""
    if isinstance(scope_value, str):
        granted_scopes = set(scope_value.split())
    else:
        granted_scopes = set(scope_value or [])
    required = settings.entra_required_scope
    if required and required not in granted_scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Token is missing required scope '{required}'.",
        )
    return decoded
