"""create contact_requests table

Revision ID: a4f1c9d27b3e
Revises: 92d68f6c152d
Create Date: 2026-07-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4f1c9d27b3e'
down_revision: Union[str, None] = '92d68f6c152d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('contact_requests',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('company', sa.String(length=255), nullable=True),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('interest', sa.String(length=50), nullable=True),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('call_requested', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('contact_requests')
