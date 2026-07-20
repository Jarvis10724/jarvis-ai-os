"""add website and divisions_json to companies

Revision ID: c4f9a17e2b6d
Revises: a23853679925
Create Date: 2026-07-16 19:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c4f9a17e2b6d'
down_revision = 'a23853679925'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('companies') as batch_op:
        batch_op.add_column(sa.Column('website', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('divisions_json', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('companies') as batch_op:
        batch_op.drop_column('divisions_json')
        batch_op.drop_column('website')
