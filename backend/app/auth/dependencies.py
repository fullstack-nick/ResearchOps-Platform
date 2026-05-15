from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.entra import EntraConfigurationError, validate_entra_token
from app.auth.service import (
    get_user_by_email,
    upsert_user_from_entra_claims,
    user_has_any_role,
)
from app.core.config import get_settings
from app.database.models import User
from app.database.session import get_session


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    return header.split(" ", 1)[1].strip()


async def _resolve_dev_user(session: AsyncSession, email: str) -> User:
    user = await get_user_by_email(session, email)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No active dev user found for '{email}'.",
        )
    return user


async def current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    settings = get_settings()
    if settings.is_entra_auth:
        token = _bearer_token(request)
        try:
            claims = await asyncio.to_thread(validate_entra_token, settings, token)
        except EntraConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        return await upsert_user_from_entra_claims(session, claims)
    requested_email = (
        request.headers.get("x-dev-user-email") or settings.dev_default_user_email
    ).strip().lower()
    return await _resolve_dev_user(session, requested_email)


CurrentUserDep = Annotated[User, Depends(current_user)]


def require_any_role(*allowed: str) -> Callable[..., Awaitable[User]]:
    async def _check(user: CurrentUserDep) -> User:
        if not user_has_any_role(user, allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(allowed)}.",
            )
        return user

    return _check
