"""add workspace_sessions

Revision ID: e5b9c2a41f76
Revises: d8a3c5f19e47
Create Date: 2026-07-19 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5b9c2a41f76'
down_revision = 'd8a3c5f19e47'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workspace_sessions',
        sa.Column('owner_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='active'),
        sa.Column('messages_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('artifacts_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workspace_sessions_owner_id', 'workspace_sessions', ['owner_id'])


def downgrade() -> None:
    op.drop_index('ix_workspace_sessions_owner_id', table_name='workspace_sessions')
    op.drop_table('workspace_sessions')
