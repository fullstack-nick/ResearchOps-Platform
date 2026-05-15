from __future__ import annotations

import asyncio
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, cast

from fastapi import HTTPException, status
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.auth.entra import EntraConfigurationError, validate_entra_token
from app.auth.service import get_role_names, get_user_by_email, upsert_user_from_entra_claims
from app.core.config import Settings, get_settings
from app.database.models import User
from app.database.session import AsyncSessionLocal


@dataclass(frozen=True)
class McpAuthContext:
    agent_user: User
    delegated_user: User
    agent_name: str
    correlation_id: str
    source_ip: str | None


_current_context: ContextVar[McpAuthContext | None] = ContextVar(
    "researchops_mcp_auth_context", default=None
)


def get_mcp_auth_context() -> McpAuthContext:
    context = _current_context.get()
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MCP tool call is missing authenticated agent context.",
        )
    return context


def set_mcp_auth_context_for_test(context: McpAuthContext) -> Token[McpAuthContext | None]:
    return _current_context.set(context)


def reset_mcp_auth_context(token: Token[McpAuthContext | None]) -> None:
    _current_context.reset(token)


class McpAuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not str(scope.get("path", "")).startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        headers = Headers(scope=scope)
        try:
            context = await resolve_mcp_context(settings, headers, scope)
        except HTTPException as exc:
            response = JSONResponse(
                {"detail": exc.detail},
                status_code=exc.status_code,
            )
            await response(scope, receive, send)
            return

        token = _current_context.set(context)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_context.reset(token)


async def resolve_mcp_context(
    settings: Settings, headers: Headers, scope: Scope
) -> McpAuthContext:
    _validate_origin(settings, headers)
    correlation_id = headers.get("x-correlation-id") or str(uuid.uuid4())
    source_ip = _source_ip(scope)
    if settings.is_entra_auth:
        return await _resolve_entra_context(settings, headers, correlation_id, source_ip)
    return await _resolve_development_context(settings, headers, correlation_id, source_ip)


def _validate_origin(settings: Settings, headers: Headers) -> None:
    origin = headers.get("origin")
    if not origin:
        return
    allowed = settings.mcp_allowed_origin_values
    if "*" not in allowed and origin not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin is not allowed for MCP requests.",
        )


def _source_ip(scope: Scope) -> str | None:
    client = cast(tuple[object, ...] | None, scope.get("client"))
    if isinstance(client, tuple) and client:
        return str(client[0])
    return None


async def _resolve_development_context(
    settings: Settings,
    headers: Headers,
    correlation_id: str,
    source_ip: str | None,
) -> McpAuthContext:
    if not settings.mcp_dev_agent_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP_DEV_AGENT_TOKEN must be configured in development mode.",
        )
    if headers.get("x-mcp-agent-token") != settings.mcp_dev_agent_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid MCP development agent token.",
        )
    delegated_email = (headers.get("x-dev-user-email") or "").strip().lower()
    if not delegated_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Dev-User-Email is required for development MCP calls.",
        )

    async with AsyncSessionLocal() as session:
        agent_user = await get_user_by_email(session, settings.mcp_service_user_email)
        delegated_user = await get_user_by_email(session, delegated_email)
        _validate_agent_user(agent_user)
        if delegated_user is None or not delegated_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"No active delegated user found for '{delegated_email}'.",
            )
        assert agent_user is not None
        assert delegated_user is not None
    return McpAuthContext(
        agent_user=agent_user,
        delegated_user=delegated_user,
        agent_name=settings.mcp_service_user_email,
        correlation_id=correlation_id,
        source_ip=source_ip,
    )


async def _resolve_entra_context(
    settings: Settings,
    headers: Headers,
    correlation_id: str,
    source_ip: str | None,
) -> McpAuthContext:
    header = headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    token = header.split(" ", 1)[1].strip()
    try:
        claims = await asyncio.to_thread(validate_entra_token, settings, token)
    except EntraConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    client_id = _claim_value(claims, "azp", "appid", "client_id")
    allowed_client_ids = settings.mcp_allowed_agent_client_id_values
    if not allowed_client_ids:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP_ALLOWED_AGENT_CLIENT_IDS must be configured in Entra mode.",
        )
    if client_id not in allowed_client_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bearer token client id is not allowed to call MCP tools.",
        )

    async with AsyncSessionLocal() as session:
        agent_user = await get_user_by_email(session, settings.mcp_service_user_email)
        delegated_user = await upsert_user_from_entra_claims(session, claims)
        _validate_agent_user(agent_user)
        assert agent_user is not None
    return McpAuthContext(
        agent_user=agent_user,
        delegated_user=delegated_user,
        agent_name=client_id,
        correlation_id=correlation_id,
        source_ip=source_ip,
    )


def _claim_value(claims: dict[str, Any], *names: str) -> str:
    for name in names:
        value = claims.get(name)
        if value:
            return str(value).strip()
    return ""


def _validate_agent_user(agent_user: User | None) -> None:
    if agent_user is None or not agent_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configured MCP service user is missing or inactive.",
        )
    if "agent_service" not in get_role_names(agent_user):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configured MCP service user is missing the agent_service role.",
        )
