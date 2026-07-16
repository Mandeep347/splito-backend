"""add email verification and password reset support

Revision ID: 0003_email_verification
Revises: 0002_notifications_updated_at
Create Date: 2026-05-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0003_email_verification"
down_revision: Union[str, None] = "0002_notifications_updated_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Add is_email_verified to users ────────────────────────────────────────
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = [c["name"] for c in inspector.get_columns("users")]

    if "is_email_verified" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column(
                "is_email_verified",
                sa.Boolean,
                nullable=False,
                server_default="false",
            ),
        )

    # ── Create user_tokens table ───────────────────────────────────────────────
    existing_tables = inspector.get_table_names()
    if "user_tokens" not in existing_tables:
        op.create_table(
            "user_tokens",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token", sa.String(64), nullable=False, unique=True),
            sa.Column("token_type", sa.String(30), nullable=False),
            sa.Column(
                "expires_at", sa.DateTime(timezone=True), nullable=False
            ),
            sa.Column(
                "is_used",
                sa.Boolean,
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_user_tokens_user_id", "user_tokens", ["user_id"])
        op.create_index("ix_user_tokens_token", "user_tokens", ["token"])


def downgrade() -> None:
    op.drop_table("user_tokens")

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c["name"] for c in inspector.get_columns("users")]
    if "is_email_verified" in existing_cols:
        op.drop_column("users", "is_email_verified")
