"""move password reset tokens to their own table

Revision ID: 0006_password_reset_tokens
Revises: 0005_email_verification_tokens
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import settings


revision: str = "0006_password_reset_tokens"
down_revision: str | None = "0005_email_verification_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = settings.database_schema


def upgrade() -> None:
    """Create password reset token rows and remove token columns from users."""

    op.create_table(
        "password_reset_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("token_hash", name="password_reset_tokens_token_hash_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_password_reset_tokens_user_id",
        "password_reset_tokens",
        ["user_id"],
        schema=SCHEMA,
    )

    # Keep any outstanding reset tokens usable after the table move.
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.password_reset_tokens
            (user_id, token_hash, expires_at, is_used, created_at, updated_at)
        SELECT
            id,
            password_reset_token_hash,
            password_reset_sent_at + interval '{settings.password_reset_token_expire_minutes} minutes',
            false,
            now(),
            now()
        FROM {SCHEMA}.users
        WHERE password_reset_token_hash IS NOT NULL
          AND password_reset_sent_at IS NOT NULL
        """
    )

    op.drop_constraint(
        "users_password_reset_token_hash_key",
        "users",
        schema=SCHEMA,
        type_="unique",
    )
    op.drop_column("users", "password_reset_sent_at", schema=SCHEMA)
    op.drop_column("users", "password_reset_token_hash", schema=SCHEMA)


def downgrade() -> None:
    """Move schema back to user-owned password reset token columns."""

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
    op.drop_index(
        "ix_password_reset_tokens_user_id",
        table_name="password_reset_tokens",
        schema=SCHEMA,
    )
    op.drop_table("password_reset_tokens", schema=SCHEMA)
