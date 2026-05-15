from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class CurrentUserRead(BaseModel):
    id: UUID
    email: str
    display_name: str
    research_group: str | None
    is_active: bool
    roles: list[str]


class DevUserOption(BaseModel):
    email: str
    display_name: str
    research_group: str | None
    roles: list[str]


class DevUserListResponse(BaseModel):
    users: list[DevUserOption]


class AuthConfigRead(BaseModel):
    auth_mode: str
    entra_client_id: str | None = None
    entra_authority: str | None = None
    entra_required_scope: str | None = None
