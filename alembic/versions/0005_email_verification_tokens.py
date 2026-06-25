"""move email verification tokens to their own table

Revision ID: 0005_email_verification_tokens
Revises: 0004_password_reset
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import settings


revision: str = "0005_email_verification_tokens"
down_revision: str | None = "0004_password_reset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = settings.database_schema


def upgrade() -> None:
    """Create verification token rows and remove token columns from users."""

    op.create_table(
        "email_verification_tokens",
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
        sa.UniqueConstraint(
            "token_hash",
            name="email_verification_tokens_token_hash_key",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_email_verification_tokens_user_id",
        "email_verification_tokens",
        ["user_id"],
        schema=SCHEMA,
    )

    # Keep old unverified users working by moving their old raw tokens as hashes.
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.email_verification_tokens
            (user_id, token_hash, expires_at, is_used, created_at, updated_at)
        SELECT
            id,
            encode(digest(email_verification_token, 'sha256'), 'hex'),
            COALESCE(email_verification_sent_at, now()) + interval '24 hours',
            false,
            now(),
            now()
        FROM {SCHEMA}.users
        WHERE email_verification_token IS NOT NULL
        """
    )

    op.drop_constraint(
        "users_email_verification_token_key",
        "users",
        schema=SCHEMA,
        type_="unique",
    )
    op.drop_column("users", "email_verification_sent_at", schema=SCHEMA)
    op.drop_column("users", "email_verification_token", schema=SCHEMA)


def downgrade() -> None:
    """Move schema back to user-owned verification token columns."""

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
    op.create_unique_constraint(
        "users_email_verification_token_key",
        "users",
        ["email_verification_token"],
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_email_verification_tokens_user_id",
        table_name="email_verification_tokens",
        schema=SCHEMA,
    )
    op.drop_table("email_verification_tokens", schema=SCHEMA)
