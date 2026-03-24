"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.Column('crawl_rules_json', sa.JSON(), nullable=True),
        sa.Column('selector_overrides_json', sa.JSON(), nullable=True),
        sa.Column('robots_txt_allowed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('last_scan_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sources_domain', 'sources', ['domain'])
    op.create_index('ix_sources_active', 'sources', ['active'])

    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('canonical_url', sa.String(2048), nullable=False),
        sa.Column('name', sa.String(512), nullable=False),
        sa.Column('brand', sa.String(255), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('product_type', sa.String(100), nullable=True),
        sa.Column('variant', sa.String(255), nullable=True),
        sa.Column('color', sa.String(100), nullable=True),
        sa.Column('size', sa.String(100), nullable=True),
        sa.Column('image_url', sa.String(2048), nullable=True),
        sa.Column('sku', sa.String(255), nullable=True),
        sa.Column('gtin', sa.String(50), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.Column('confidence', sa.Float(), nullable=False, default=0.0),
        sa.Column('raw_data_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('canonical_product_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['canonical_product_id'], ['products.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_products_source_id', 'products', ['source_id'])
    op.create_index('ix_products_category', 'products', ['category'])
    op.create_index('ix_products_active', 'products', ['active'])
    op.create_index('ix_products_canonical_url', 'products', ['canonical_url'])
    op.create_index('ix_products_sku', 'products', ['sku'])

    op.create_table(
        'price_observations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('price_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('currency', sa.String(10), nullable=True),
        sa.Column('list_price_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('in_stock', sa.Boolean(), nullable=True),
        sa.Column('stock_quantity', sa.Integer(), nullable=True),
        sa.Column('raw_json', sa.JSON(), nullable=True),
        sa.Column('crawl_run_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_price_observations_product_id', 'price_observations', ['product_id'])
    op.create_index('ix_price_observations_observed_at', 'price_observations', ['observed_at'])

    op.create_table(
        'price_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('old_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('new_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('old_currency', sa.String(10), nullable=True),
        sa.Column('new_currency', sa.String(10), nullable=True),
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('change_percent', sa.Float(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_price_changes_product_id', 'price_changes', ['product_id'])
    op.create_index('ix_price_changes_changed_at', 'price_changes', ['changed_at'])
    op.create_index('ix_price_changes_change_type', 'price_changes', ['change_type'])

    op.create_table(
        'crawl_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='running'),
        sa.Column('pages_visited', sa.Integer(), nullable=False, default=0),
        sa.Column('products_found', sa.Integer(), nullable=False, default=0),
        sa.Column('products_updated', sa.Integer(), nullable=False, default=0),
        sa.Column('price_changes_detected', sa.Integer(), nullable=False, default=0),
        sa.Column('errors_count', sa.Integer(), nullable=False, default=0),
        sa.Column('error_messages', sa.JSON(), nullable=True),
        sa.Column('stats_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_crawl_runs_source_id', 'crawl_runs', ['source_id'])
    op.create_index('ix_crawl_runs_started_at', 'crawl_runs', ['started_at'])
    op.create_index('ix_crawl_runs_status', 'crawl_runs', ['status'])


def downgrade() -> None:
    op.drop_table('crawl_runs')
    op.drop_table('price_changes')
    op.drop_table('price_observations')
    op.drop_table('products')
    op.drop_table('sources')
