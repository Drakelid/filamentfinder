"""Null out relative image URLs that were stored without a host

Revision ID: 010_fix_relative_image_urls
Revises: 009_add_fts_index
Create Date: 2026-03-27
"""
from typing import Sequence, Union

from alembic import op


revision: str = "010_fix_relative_image_urls"
down_revision: Union[str, None] = "009_add_fts_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Root-relative paths like /images/product/... resolve against the app origin in the
    # browser instead of the source store's domain, producing 404s.  Clearing them allows
    # the next crawl to re-fetch and store the correctly-absolutised URL.
    op.execute(
        "UPDATE products SET image_url = NULL "
        "WHERE image_url IS NOT NULL AND image_url NOT LIKE 'http%'"
    )


def downgrade() -> None:
    pass
