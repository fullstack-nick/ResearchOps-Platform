from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import ROLE_NAMES, Role, User, UserRole


def get_role_names(user: User) -> set[str]:
    return {assignment.role.name for assignment in user.roles if assignment.role}


def user_has_any_role(user: User, allowed: tuple[str, ...]) -> bool:
    return bool(get_role_names(user) & set(allowed))


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User)
        .where(User.email == email.lower())
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    return result.scalars().unique().one_or_none()


async def get_user_by_entra_oid(session: AsyncSession, oid: str) -> User | None:
    result = await session.execute(
        select(User)
        .where(User.entra_oid == oid)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    return result.scalars().unique().one_or_none()


async def get_active_users_with_roles(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User)
        .where(User.is_active.is_(True))
        .order_by(User.email)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    return list(result.scalars().unique().all())


async def upsert_user_from_entra_claims(
    session: AsyncSession, claims: dict[str, Any]
) -> User:
    oid = str(claims.get("oid") or claims.get("sub") or "").strip()
    email = (
        claims.get("preferred_username")
        or claims.get("upn")
        or claims.get("email")
        or ""
    )
    email = str(email).strip().lower()
    display_name = str(claims.get("name") or email or oid)
    if not (oid or email):
        raise ValueError("Entra ID token is missing oid/email claims.")

    existing = (await get_user_by_entra_oid(session, oid)) if oid else None
    if existing is None and email:
        existing = await get_user_by_email(session, email)
    if existing is not None:
        if oid and not existing.entra_oid:
            existing.entra_oid = oid
        if not existing.display_name:
            existing.display_name = display_name
        await session.commit()
        await session.refresh(existing)
        return existing

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=email or f"{oid}@unknown.entra",
        display_name=display_name,
        entra_oid=oid or None,
        is_active=True,
        research_group=None,
    )
    session.add(user)
    role_claims_raw: Any = claims.get("roles") or []
    role_claims: list[str]
    if isinstance(role_claims_raw, str):
        role_claims = [role_claims_raw]
    elif isinstance(role_claims_raw, list):
        role_claims = [str(item) for item in role_claims_raw]  # type: ignore[redundant-cast]
    else:
        role_claims = []
    valid_role_names = {name for name in role_claims if name in ROLE_NAMES} or {"researcher"}
    roles_result = await session.execute(
        select(Role).where(Role.name.in_(valid_role_names))
    )
    for role in roles_result.scalars().all():
        session.add(UserRole(user_id=user_id, role_id=role.id))
    await session.commit()
    loaded = await get_user_by_email(session, user.email)
    if loaded is None:
        raise RuntimeError("Failed to load newly created Entra user.")
    return loaded
