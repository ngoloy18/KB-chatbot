"""add password reset fields to users

Revision ID: 0004_password_reset
Revises: 0003_refresh_tokens
Create Date: 2026-06-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.config import settings


revision: str = "0004_password_reset"
down_revision: str | None = "0003_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Keep migration schema aligned with runtime model configuration.
SCHEMA = settings.database_schema


def upgrade() -> None:
    """Add password reset token columns to users."""

    op.add_column(
        "users",
        sa.Column("password_reset_token_hash", sa.String(length=64), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "users",
        sa.Column("password_reset_sent_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_unique_constraint(
        "users_password_reset_token_hash_key",
        "users",
        ["password_reset_token_hash"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Remove password reset token columns from users."""

    op.drop_constraint(
        "users_password_reset_token_hash_key",
        "users",
        schema=SCHEMA,
        type_="unique",
    )
    op.drop_column("users", "password_reset_sent_at", schema=SCHEMA)
    op.drop_column("users", "password_reset_token_hash", schema=SCHEMA)
