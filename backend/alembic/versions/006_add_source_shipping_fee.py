"""Add shipping_fee to sources

Revision ID: 006_add_source_shipping_fee
Revises: 005_add_shipping_fields
Create Date: 2026-01-22 21:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_source_shipping_fee'
down_revision: Union[str, None] = '005_add_shipping_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sources', sa.Column('shipping_fee', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('sources', 'shipping_fee')
