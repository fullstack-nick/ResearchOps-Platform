"""phase 2 azure extraction schema

Revision ID: 202605140002
Revises: 202605140001
Create Date: 2026-05-14 00:02:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202605140002"
down_revision: str | Sequence[str] | None = "202605140001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status in ('uploaded', 'extraction_pending', 'extracting', 'extracted', "
        "'extraction_failed', 'archived')",
    )

    op.add_column(
        "document_versions",
        sa.Column(
            "storage_provider",
            sa.String(length=40),
            server_default="local",
            nullable=False,
        ),
    )
    op.add_column(
        "document_versions",
        sa.Column("storage_container", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column("storage_object_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column("storage_url", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_document_versions_storage_provider",
        "document_versions",
        "storage_provider in ('local', 'azure_blob')",
    )

    op.create_table(
        "extraction_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("model_id", sa.String(length=120), nullable=False),
        sa.Column(
            "missing_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('pending', 'processing', 'completed', 'failed')",
            name="ck_extraction_runs_status",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_extraction_runs_status_created",
        "extraction_runs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_extraction_runs_document_created",
        "extraction_runs",
        ["document_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "extracted_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("value_type", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column(
            "source_regions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("raw_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_missing", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("corrected_value", sa.Text(), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("corrected_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["corrected_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"], ["extraction_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "extraction_run_id",
            "field_key",
            name="uq_extracted_fields_run_field",
        ),
    )
    op.create_index(
        "ix_extracted_fields_document_key",
        "extracted_fields",
        ["document_id", "field_key"],
        unique=False,
    )

    op.create_table(
        "extracted_line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("unit_price", sa.Float(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column(
            "source_regions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("raw_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"], ["extraction_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "extraction_run_id",
            "item_index",
            name="uq_extracted_line_items_run_index",
        ),
    )
    op.create_index(
        "ix_extracted_line_items_document",
        "extracted_line_items",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_extracted_line_items_document", table_name="extracted_line_items")
    op.drop_table("extracted_line_items")
    op.drop_index("ix_extracted_fields_document_key", table_name="extracted_fields")
    op.drop_table("extracted_fields")
    op.drop_index("ix_extraction_runs_document_created", table_name="extraction_runs")
    op.drop_index("ix_extraction_runs_status_created", table_name="extraction_runs")
    op.drop_table("extraction_runs")

    op.drop_constraint(
        "ck_document_versions_storage_provider", "document_versions", type_="check"
    )
    op.drop_column("document_versions", "storage_url")
    op.drop_column("document_versions", "storage_object_key")
    op.drop_column("document_versions", "storage_container")
    op.drop_column("document_versions", "storage_provider")

    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.execute(
        "update documents set status = 'uploaded' "
        "where status not in ('uploaded', 'archived')"
    )
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status in ('uploaded', 'archived')",
    )
