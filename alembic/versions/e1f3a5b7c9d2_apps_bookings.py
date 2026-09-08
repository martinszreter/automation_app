"""apps_bookings: demo bookings + setup details for the /apps admin list (W2-A4)

Revision ID: e1f3a5b7c9d2
Revises: d7a2b9c4e6f1
Create Date: 2026-09-08 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f3a5b7c9d2"
down_revision: Union[str, None] = "d7a2b9c4e6f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "apps_bookings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="new"),
        sa.Column("restaurant_name", sa.String(length=160), nullable=False),
        sa.Column("contact", sa.String(length=160), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("booking_date", sa.Date(), nullable=True),
        sa.Column("booking_time", sa.String(length=16), nullable=True),
        sa.Column("guests", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("opening_hours", sa.Text(), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_apps_bookings_created_at", "apps_bookings", ["created_at"])
    op.create_index("ix_apps_bookings_session_id", "apps_bookings", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_apps_bookings_session_id", table_name="apps_bookings")
    op.drop_index("ix_apps_bookings_created_at", table_name="apps_bookings")
    op.drop_table("apps_bookings")
