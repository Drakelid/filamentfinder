"""Add config table for application settings

Revision ID: 004
Revises: 003
Create Date: 2026-01-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('encrypted', sa.Boolean(), nullable=True, default=False),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_config_id'), 'config', ['id'], unique=False)
    op.create_index(op.f('ix_config_key'), 'config', ['key'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_config_key'), table_name='config')
    op.drop_index(op.f('ix_config_id'), table_name='config')
    op.drop_table('config')
