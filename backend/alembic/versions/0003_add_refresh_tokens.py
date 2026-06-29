"""add refresh token sessions

Revision ID: 0003_refresh_tokens
Revises: 0002_email_verification
Create Date: 2026-06-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import settings


revision: str = "0003_refresh_tokens"
down_revision: str | None = "0002_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Keep migration schema aligned with runtime model configuration.
SCHEMA = settings.database_schema


def upgrade() -> None:
    """Create refresh token storage for logout and token rotation."""

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_id", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
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
            ["user_id"],
            [f"{SCHEMA}.users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="refresh_tokens_token_hash_key"),
        sa.UniqueConstraint("token_id", name="refresh_tokens_token_id_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_refresh_tokens_user_id",
        "refresh_tokens",
        ["user_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Remove refresh token storage."""

    op.drop_index("idx_refresh_tokens_user_id", table_name="refresh_tokens", schema=SCHEMA)
    op.drop_table("refresh_tokens", schema=SCHEMA)
