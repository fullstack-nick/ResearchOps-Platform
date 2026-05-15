"""phase 5 mcp agent actions

Revision ID: 202605140005
Revises: 202605140004
Create Date: 2026-05-14 00:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202605140005"
down_revision: str | Sequence[str] | None = "202605140004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGENT_ROLE_ID = "00000000-0000-4000-8000-000000000108"
AGENT_USER_ID = "00000000-0000-4000-8000-000000000301"


def upgrade() -> None:
    op.create_table(
        "agent_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("agent_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_name", sa.String(length=200), nullable=False),
        sa.Column("delegated_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('completed', 'failed', 'denied')",
            name="ck_agent_actions_status",
        ),
        sa.ForeignKeyConstraint(["agent_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["delegated_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_actions_tool_created",
        "agent_actions",
        ["tool_name", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_actions_delegated_created",
        "agent_actions",
        ["delegated_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_actions_document_created",
        "agent_actions",
        ["document_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_actions_workflow_created",
        "agent_actions",
        ["workflow_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_actions_correlation",
        "agent_actions",
        ["correlation_id"],
        unique=False,
    )

    roles = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    users = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("email", sa.String),
        sa.column("display_name", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("research_group", sa.String),
    )
    user_roles = sa.table(
        "user_roles",
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("role_id", postgresql.UUID(as_uuid=True)),
    )
    op.bulk_insert(
        roles,
        [
            {
                "id": AGENT_ROLE_ID,
                "name": "agent_service",
                "description": "Call controlled MCP tools on behalf of users",
            }
        ],
    )
    op.bulk_insert(
        users,
        [
            {
                "id": AGENT_USER_ID,
                "email": "agent.researchops@example.test",
                "display_name": "ResearchOps Agent Service",
                "is_active": True,
                "research_group": "operations",
            }
        ],
    )
    op.bulk_insert(
        user_roles,
        [{"user_id": AGENT_USER_ID, "role_id": AGENT_ROLE_ID}],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_actions_correlation", table_name="agent_actions")
    op.drop_index("ix_agent_actions_workflow_created", table_name="agent_actions")
    op.drop_index("ix_agent_actions_document_created", table_name="agent_actions")
    op.drop_index("ix_agent_actions_delegated_created", table_name="agent_actions")
    op.drop_index("ix_agent_actions_tool_created", table_name="agent_actions")
    op.drop_table("agent_actions")

    user_roles = sa.table(
        "user_roles",
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("role_id", postgresql.UUID(as_uuid=True)),
    )
    users = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
    )
    roles = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
    )
    op.execute(user_roles.delete().where(user_roles.c.user_id == AGENT_USER_ID))
    op.execute(users.delete().where(users.c.id == AGENT_USER_ID))
    op.execute(roles.delete().where(roles.c.id == AGENT_ROLE_ID))
