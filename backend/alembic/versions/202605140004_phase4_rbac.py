"""phase 4 rbac, approval workflow, and entra identity columns

Revision ID: 202605140004
Revises: 202605140003
Create Date: 2026-05-14 00:04:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202605140004"
down_revision: str | Sequence[str] | None = "202605140003"
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
EXTRA_USERS = (
    {
        "id": "00000000-0000-4000-8000-000000000201",
        "email": "researcher.alice@example.test",
        "display_name": "Alice Researcher",
        "research_group": "genomics",
        "roles": ("researcher",),
    },
    {
        "id": "00000000-0000-4000-8000-000000000202",
        "email": "lead.bob@example.test",
        "display_name": "Bob Group Lead",
        "research_group": "genomics",
        "roles": ("group_lead",),
    },
    {
        "id": "00000000-0000-4000-8000-000000000203",
        "email": "finance.carol@example.test",
        "display_name": "Carol Finance",
        "research_group": "operations",
        "roles": ("finance",),
    },
    {
        "id": "00000000-0000-4000-8000-000000000204",
        "email": "hr.dan@example.test",
        "display_name": "Dan HR",
        "research_group": "operations",
        "roles": ("hr",),
    },
    {
        "id": "00000000-0000-4000-8000-000000000205",
        "email": "it.eve@example.test",
        "display_name": "Eve IT",
        "research_group": "operations",
        "roles": ("it",),
    },
    {
        "id": "00000000-0000-4000-8000-000000000206",
        "email": "admin.frank@example.test",
        "display_name": "Frank Admin",
        "research_group": "operations",
        "roles": ("operations_admin", "system_admin"),
    },
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("entra_oid", sa.String(length=80), nullable=True),
    )
    op.create_unique_constraint("uq_users_entra_oid", "users", ["entra_oid"])
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("research_group", sa.String(length=80), nullable=True),
    )
    demo_user_table = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("research_group", sa.String),
    )
    op.execute(
        demo_user_table.update()
        .where(demo_user_table.c.id == DEMO_USER_ID)
        .values(research_group="operations")
    )

    op.add_column(
        "documents",
        sa.Column("research_group", sa.String(length=80), nullable=True),
    )

    op.add_column(
        "workflow_steps",
        sa.Column(
            "step_order",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "workflow_steps",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_workflow_steps_workflow_order",
        "workflow_steps",
        ["workflow_id", "step_order"],
    )

    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approver_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision in ('approved', 'rejected')",
            name="ck_approvals_decision",
        ),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workflow_step_id"], ["workflow_steps.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approvals_workflow_step", "approvals", ["workflow_step_id"], unique=False
    )
    op.create_index(
        "ix_approvals_workflow_created",
        "approvals",
        ["workflow_id", "created_at"],
        unique=False,
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
        users,
        [
            {
                "id": entry["id"],
                "email": entry["email"],
                "display_name": entry["display_name"],
                "is_active": True,
                "research_group": entry["research_group"],
            }
            for entry in EXTRA_USERS
        ],
    )
    op.bulk_insert(
        user_roles,
        [
            {"user_id": entry["id"], "role_id": ROLE_IDS[role]}
            for entry in EXTRA_USERS
            for role in entry["roles"]
        ],
    )


def downgrade() -> None:
    # Extra seeded users and their role assignments are left in place: rolling
    # the schema all the way back to ``base`` will drop ``users`` and
    # ``user_roles`` entirely, and deleting them earlier would violate foreign
    # keys from ``documents``/``audit_events`` rows that may still exist.
    op.drop_index("ix_approvals_workflow_created", table_name="approvals")
    op.drop_index("ix_approvals_workflow_step", table_name="approvals")
    op.drop_table("approvals")

    op.drop_constraint(
        "uq_workflow_steps_workflow_order", "workflow_steps", type_="unique"
    )
    op.drop_column("workflow_steps", "completed_at")
    op.drop_column("workflow_steps", "step_order")

    op.drop_column("documents", "research_group")

    op.drop_column("users", "research_group")
    op.drop_column("users", "is_active")
    op.drop_constraint("uq_users_entra_oid", "users", type_="unique")
    op.drop_column("users", "entra_oid")
