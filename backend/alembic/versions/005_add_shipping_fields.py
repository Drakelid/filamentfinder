"""Add shipping fields to sources and price observations

Revision ID: 005_add_shipping_fields
Revises: 004
Create Date: 2026-01-20 20:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_shipping_fields'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sources', sa.Column('shipping_profile_json', sa.JSON(), nullable=True))

    op.add_column('price_observations', sa.Column('shipping_amount', sa.Numeric(12, 2), nullable=True))
    op.add_column('price_observations', sa.Column('shipping_currency', sa.String(length=10), nullable=True))
    op.add_column('price_observations', sa.Column('total_price_amount', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('price_observations', 'total_price_amount')
    op.drop_column('price_observations', 'shipping_currency')
    op.drop_column('price_observations', 'shipping_amount')

    op.drop_column('sources', 'shipping_profile_json')
