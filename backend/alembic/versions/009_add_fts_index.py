"""Add FTS index

Revision ID: 009_add_fts_index
Revises: 008_add_price_alerts
Create Date: 2026-03-26
"""
from typing import Sequence, Union

from alembic import op


revision: str = "009_add_fts_index"
down_revision: Union[str, None] = "008_add_price_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE products
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
          to_tsvector('english',
            coalesce(name,'') || ' ' || coalesce(brand,'') || ' ' ||
            coalesce(product_type,'') || ' ' || coalesce(color,'')
          )
        ) STORED
        """
    )
    op.execute("CREATE INDEX idx_products_search_vector ON products USING GIN(search_vector)")
    op.execute("UPDATE products SET name = name")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_products_search_vector")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS search_vector")
