"""ensure notifications table has updated_at column

Revision ID: 0002_notifications_updated_at
Revises: 0001_initial
Create Date: 2026-05-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_notifications_updated_at"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The notifications table was created in 0001_initial without updated_at
    # (because it was defined manually in the spec without it).
    # TimestampMixin adds updated_at — add it here if it doesn't exist yet.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("notifications")]

    if "updated_at" not in existing_columns:
        op.add_column(
            "notifications",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("notifications")]
    if "updated_at" in existing_columns:
        op.drop_column("notifications", "updated_at")
