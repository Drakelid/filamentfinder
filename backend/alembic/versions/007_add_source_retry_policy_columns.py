"""Add missing source retry policy and tracking columns

Revision ID: 007_retry_policy_columns
Revises: 006_add_source_shipping_fee
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa


revision = '007_retry_policy_columns'
down_revision = '006_add_source_shipping_fee'
branch_labels = None
depends_on = None


def _column_missing(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name not in columns


def upgrade() -> None:
    bind = op.get_bind()
    columns_to_add = [
        ('retry_policy_json', sa.Column('retry_policy_json', sa.JSON(), nullable=True)),
        ('crawl_duration_stats_json', sa.Column('crawl_duration_stats_json', sa.JSON(), nullable=True)),
        ('alert_settings_json', sa.Column('alert_settings_json', sa.JSON(), nullable=True)),
        ('failure_streak', sa.Column('failure_streak', sa.Integer(), nullable=False, server_default='0')),
        ('next_retry_at', sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True)),
    ]
    for name, column in columns_to_add:
        if _column_missing(bind, 'sources', name):
            op.add_column('sources', column)


def downgrade() -> None:
    bind = op.get_bind()
    columns_to_drop = ['next_retry_at', 'failure_streak', 'alert_settings_json', 'crawl_duration_stats_json', 'retry_policy_json']
    for name in columns_to_drop:
        if not _column_missing(bind, 'sources', name):
            op.drop_column('sources', name)
