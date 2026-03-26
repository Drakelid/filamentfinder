"""Add price alerts

Revision ID: 008_add_price_alerts
Revises: 007_retry_policy_columns
Create Date: 2026-03-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "008_add_price_alerts"
down_revision: Union[str, None] = "007_retry_policy_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.create_table(
        "price_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("target_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_alerts_product_id", "price_alerts", ["product_id"])
    op.create_index("ix_price_alerts_active", "price_alerts", ["active"])


def downgrade() -> None:
    op.drop_index("ix_price_alerts_active", table_name="price_alerts")
    op.drop_index("ix_price_alerts_product_id", table_name="price_alerts")
    op.drop_table("price_alerts")
