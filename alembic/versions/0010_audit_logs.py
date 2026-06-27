"""add audit logs

Revision ID: 0010_audit_logs
Revises: 0009_pgvector_hnsw_index
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import settings


revision: str = "0010_audit_logs"
down_revision: str | None = "0009_pgvector_hnsw_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = settings.database_schema


def upgrade() -> None:
    """Create an append-only table for important user and admin actions."""

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            [f"{SCHEMA}.users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_audit_logs_actor_user_id",
        "audit_logs",
        ["actor_user_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_audit_logs_resource",
        "audit_logs",
        ["resource_type", "resource_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_audit_logs_action_created_at",
        "audit_logs",
        ["action", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Remove audit logs."""

    op.drop_index(
        "idx_audit_logs_action_created_at",
        table_name="audit_logs",
        schema=SCHEMA,
    )
    op.drop_index(
        "idx_audit_logs_resource",
        table_name="audit_logs",
        schema=SCHEMA,
    )
    op.drop_index(
        "idx_audit_logs_actor_user_id",
        table_name="audit_logs",
        schema=SCHEMA,
    )
    op.drop_table("audit_logs", schema=SCHEMA)
