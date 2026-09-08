"""x_autopilot_plans: paused_at + agent_name (W2-A2 panel pause/resume)

Revision ID: d7a2b9c4e6f1
Revises: c3e8a1b94d70
Create Date: 2026-09-08 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7a2b9c4e6f1"
down_revision: Union[str, None] = "c3e8a1b94d70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("x_autopilot_plans", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("x_autopilot_plans", sa.Column("agent_name", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("x_autopilot_plans", "agent_name")
    op.drop_column("x_autopilot_plans", "paused_at")
