"""add email verification to users

Revision ID: 0002_email_verification
Revises: 0001_initial_kb_schema
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.config import settings


revision: str = "0002_email_verification"
down_revision: str | None = "0001_initial_kb_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Keep migration schema aligned with runtime model configuration.
SCHEMA = settings.database_schema


def upgrade() -> None:
    """Add email verification fields to existing users."""

    op.add_column(
        "users",
        sa.Column(
            "is_email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "users",
        sa.Column("email_verification_token", sa.String(length=255), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "users",
        sa.Column("email_verification_sent_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    # Existing users were created before verification existed, so keep them usable.
    op.execute(f"UPDATE {SCHEMA}.users SET is_email_verified = true")
    op.create_unique_constraint(
        "users_email_verification_token_key",
        "users",
        ["email_verification_token"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Remove email verification fields from users."""

    op.drop_constraint(
        "users_email_verification_token_key",
        "users",
        schema=SCHEMA,
        type_="unique",
    )
    op.drop_column("users", "email_verification_sent_at", schema=SCHEMA)
    op.drop_column("users", "email_verification_token", schema=SCHEMA)
    op.drop_column("users", "is_email_verified", schema=SCHEMA)
