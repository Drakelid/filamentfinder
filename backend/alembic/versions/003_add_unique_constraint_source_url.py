"""Add unique constraint for source_id and canonical_url

Revision ID: 003
Revises: 002
Create Date: 2026-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint to prevent duplicate product URLs per source
    op.create_unique_constraint(
        'uq_products_source_url',
        'products',
        ['source_id', 'canonical_url']
    )


def downgrade() -> None:
    op.drop_constraint('uq_products_source_url', 'products', type_='unique')
