"""create x_autopilot_plans table

Revision ID: c3e8a1b94d70
Revises: a4f1c9d27b3e
Create Date: 2026-09-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e8a1b94d70"
down_revision: Union[str, None] = "a4f1c9d27b3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "x_autopilot_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("stripe_email", sa.String(length=320), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACTIVE", "CANCELED", "REFUNDED", name="x_autopilot_plan_status"),
            nullable=False,
        ),
        sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_checkout_session_id"),
    )
    op.create_index("ix_x_autopilot_plans_email", "x_autopilot_plans", ["email"])
    op.create_index(
        "ix_x_autopilot_plans_stripe_payment_intent_id",
        "x_autopilot_plans",
        ["stripe_payment_intent_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_x_autopilot_plans_stripe_payment_intent_id", table_name="x_autopilot_plans")
    op.drop_index("ix_x_autopilot_plans_email", table_name="x_autopilot_plans")
    op.drop_table("x_autopilot_plans")
    sa.Enum(name="x_autopilot_plan_status").drop(op.get_bind(), checkfirst=True)
