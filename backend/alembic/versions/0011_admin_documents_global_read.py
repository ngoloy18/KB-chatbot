"""make admin documents globally readable

Revision ID: 0011_admin_documents_global_read
Revises: 0010_audit_logs
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.config import settings


revision: str = "0011_admin_documents_global_read"
down_revision: str | None = "0010_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = settings.database_schema
# Earlier uploads were admin-only but did not persist their creator. Limit this
# legacy backfill to documents created before per-user uploads were introduced.
LEGACY_ADMIN_UPLOAD_CUTOFF = "2026-07-09T09:02:23+00:00"


def upgrade() -> None:
    """Add global read access and enable it for existing admin-owned documents."""

    op.add_column(
        "documents",
        sa.Column(
            "is_global_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema=SCHEMA,
    )
    op.execute(
        f"""
        UPDATE {SCHEMA}.documents AS document
        SET is_global_read = TRUE
        WHERE (
            document.created_by IS NULL
            AND document.created_at
                < TIMESTAMPTZ '{LEGACY_ADMIN_UPLOAD_CUTOFF}'
        )
        OR EXISTS (
            SELECT 1
            FROM {SCHEMA}.users AS creator
            WHERE creator.id = document.created_by
              AND creator.role = 'admin'
        )
        OR EXISTS (
            SELECT 1
            FROM {SCHEMA}.document_permissions AS permission
            JOIN {SCHEMA}.users AS permission_user
              ON permission_user.id = permission.user_id
            WHERE permission.document_id = document.id
              AND permission.permission = 'owner'
              AND permission_user.role = 'admin'
        )
        """
    )
    op.create_index(
        "idx_documents_is_global_read",
        "documents",
        ["is_global_read"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Remove document-level global read access."""

    op.drop_index(
        "idx_documents_is_global_read",
        table_name="documents",
        schema=SCHEMA,
    )
    op.drop_column("documents", "is_global_read", schema=SCHEMA)
