from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.sql import ColumnElement

from app.auth.service import get_role_names
from app.database.models import Document, User

ADMIN_ROLES = ("operations_admin", "system_admin")
WORKFLOW_TYPE_BY_ROLE: dict[str, frozenset[str]] = {
    "finance": frozenset({"procurement"}),
    "hr": frozenset({"hr_onboarding"}),
    "it": frozenset({"hr_onboarding"}),
}


def is_admin(user: User) -> bool:
    return bool(set(ADMIN_ROLES) & get_role_names(user))


def allowed_workflow_types(user: User) -> set[str]:
    allowed: set[str] = set()
    for role in get_role_names(user):
        allowed.update(WORKFLOW_TYPE_BY_ROLE.get(role, frozenset()))
    return allowed


def document_visibility_filter(user: User) -> ColumnElement[bool] | None:
    if is_admin(user):
        return None
    conditions: list[ColumnElement[bool]] = [Document.owner_user_id == user.id]
    roles = get_role_names(user)
    if "group_lead" in roles and user.research_group:
        conditions.append(Document.research_group == user.research_group)
    workflow_types = allowed_workflow_types(user)
    if workflow_types:
        conditions.append(Document.workflow_type.in_(workflow_types))
    return or_(*conditions)


def user_can_access_document(user: User, document: Document) -> bool:
    if is_admin(user):
        return True
    if document.owner_user_id == user.id:
        return True
    roles = get_role_names(user)
    if (
        "group_lead" in roles
        and user.research_group
        and document.research_group == user.research_group
    ):
        return True
    return document.workflow_type in allowed_workflow_types(user)


def assert_document_access(user: User, document: Document) -> None:
    if not user_can_access_document(user, document):
        # 404 keeps existence private to the caller's tenant of roles.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
