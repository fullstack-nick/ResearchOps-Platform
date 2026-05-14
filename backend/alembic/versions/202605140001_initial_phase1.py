"""initial phase 1 schema

Revision ID: 202605140001
Revises:
Create Date: 2026-05-14 00:01:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202605140001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_USER_ID = "00000000-0000-4000-8000-000000000001"
ROLE_IDS = {
    "researcher": "00000000-0000-4000-8000-000000000101",
    "group_lead": "00000000-0000-4000-8000-000000000102",
    "finance": "00000000-0000-4000-8000-000000000103",
    "hr": "00000000-0000-4000-8000-000000000104",
    "it": "00000000-0000-4000-8000-000000000105",
    "operations_admin": "00000000-0000-4000-8000-000000000106",
    "system_admin": "00000000-0000-4000-8000-000000000107",
}


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("safe_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("workflow_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "workflow_type in ('procurement', 'hr_onboarding', 'grants', 'contracts', 'reports')",
            name="ck_documents_workflow_type",
        ),
        sa.CheckConstraint("status in ('uploaded', 'archived')", name="ck_documents_status"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_documents_workflow_type_status",
        "documents",
        ["workflow_type", "status"],
        unique=False,
    )
    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_document_version",
        ),
    )
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_step", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "workflow_type in ('procurement', 'hr_onboarding', 'grants', 'contracts', 'reports')",
            name="ck_workflows_workflow_type",
        ),
        sa.CheckConstraint(
            "status in ('awaiting_review', 'approved', 'rejected', 'completed', 'failed')",
            name="ck_workflows_status",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index(
        "ix_workflows_type_status",
        "workflows",
        ["workflow_type", "status"],
        unique=False,
    )
    op.create_table(
        "workflow_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("assigned_role", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('pending', 'completed', 'skipped')",
            name="ck_workflow_steps_status",
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("before_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source_ip", sa.String(length=80), nullable=True),
        sa.Column("correlation_id", sa.String(length=80), nullable=False),
        sa.CheckConstraint(
            "actor_type in ('user', 'agent', 'system')",
            name="ck_audit_events_actor_type",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_audit_events_document_timestamp",
        "audit_events",
        ["document_id", "timestamp"],
        unique=False,
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"], unique=False)

    users = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("email", sa.String),
        sa.column("display_name", sa.String),
    )
    roles = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    user_roles = sa.table(
        "user_roles",
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("role_id", postgresql.UUID(as_uuid=True)),
    )
    op.bulk_insert(
        users,
        [
            {
                "id": DEMO_USER_ID,
                "email": "demo.researchops@example.test",
                "display_name": "Demo Operations User",
            }
        ],
    )
    op.bulk_insert(
        roles,
        [
            {
                "id": ROLE_IDS["researcher"],
                "name": "researcher",
                "description": "Upload and view own documents",
            },
            {
                "id": ROLE_IDS["group_lead"],
                "name": "group_lead",
                "description": "Approve group documents",
            },
            {
                "id": ROLE_IDS["finance"],
                "name": "finance",
                "description": "Review procurement and finance documents",
            },
            {
                "id": ROLE_IDS["hr"],
                "name": "hr",
                "description": "Review HR onboarding documents",
            },
            {
                "id": ROLE_IDS["it"],
                "name": "it",
                "description": "Review IT account and access tasks",
            },
            {
                "id": ROLE_IDS["operations_admin"],
                "name": "operations_admin",
                "description": "Monitor workflows and export audit logs",
            },
            {
                "id": ROLE_IDS["system_admin"],
                "name": "system_admin",
                "description": "Manage platform configuration",
            },
        ],
    )
    op.bulk_insert(
        user_roles,
        [
            {"user_id": DEMO_USER_ID, "role_id": ROLE_IDS["researcher"]},
            {"user_id": DEMO_USER_ID, "role_id": ROLE_IDS["operations_admin"]},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_document_timestamp", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("workflow_steps")
    op.drop_index("ix_workflows_type_status", table_name="workflows")
    op.drop_table("workflows")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_workflow_type_status", table_name="documents")
    op.drop_table("documents")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
