"""Add price change tracking columns to products

Revision ID: 002
Revises: 001
Create Date: 2026-01-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('products', sa.Column('latest_change_percent', sa.Float(), nullable=True))
    op.add_column('products', sa.Column('latest_change_type', sa.String(50), nullable=True))
    op.add_column('products', sa.Column('latest_change_at', sa.DateTime(timezone=True), nullable=True))
    
    op.create_index('ix_products_latest_change_percent', 'products', ['latest_change_percent'])
    op.create_index('ix_products_latest_change_at', 'products', ['latest_change_at'])


def downgrade() -> None:
    op.drop_index('ix_products_latest_change_at', table_name='products')
    op.drop_index('ix_products_latest_change_percent', table_name='products')
    
    op.drop_column('products', 'latest_change_at')
    op.drop_column('products', 'latest_change_type')
    op.drop_column('products', 'latest_change_percent')
