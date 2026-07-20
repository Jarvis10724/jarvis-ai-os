"""add memory_entries and memory_links tables

Revision ID: e7a1f4c9b210
Revises: c4f9a17e2b6d
Create Date: 2026-07-17 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'e7a1f4c9b210'
down_revision = 'c4f9a17e2b6d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('memory_entries',
    sa.Column('owner_id', sa.String(), nullable=False),
    sa.Column('company_id', sa.String(), nullable=True),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('source_ref', sa.String(length=500), nullable=True),
    sa.Column('embedding_json', sa.Text(), nullable=True),
    sa.Column('embedding_model', sa.String(length=100), nullable=True),
    sa.Column('extra_json', sa.Text(), nullable=True),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_memory_entries_owner_id', 'memory_entries', ['owner_id'])
    op.create_index('ix_memory_entries_company_id', 'memory_entries', ['company_id'])
    op.create_index('ix_memory_entries_kind', 'memory_entries', ['kind'])
    op.create_index('ix_memory_entries_owner_company', 'memory_entries', ['owner_id', 'company_id'])

    op.create_table('memory_links',
    sa.Column('from_id', sa.String(), nullable=False),
    sa.Column('to_id', sa.String(), nullable=False),
    sa.Column('relation', sa.String(length=50), nullable=False),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['from_id'], ['memory_entries.id'], ),
    sa.ForeignKeyConstraint(['to_id'], ['memory_entries.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_memory_links_from_id', 'memory_links', ['from_id'])
    op.create_index('ix_memory_links_to_id', 'memory_links', ['to_id'])


def downgrade() -> None:
    op.drop_index('ix_memory_links_to_id', table_name='memory_links')
    op.drop_index('ix_memory_links_from_id', table_name='memory_links')
    op.drop_table('memory_links')

    op.drop_index('ix_memory_entries_owner_company', table_name='memory_entries')
    op.drop_index('ix_memory_entries_kind', table_name='memory_entries')
    op.drop_index('ix_memory_entries_company_id', table_name='memory_entries')
    op.drop_index('ix_memory_entries_owner_id', table_name='memory_entries')
    op.drop_table('memory_entries')
