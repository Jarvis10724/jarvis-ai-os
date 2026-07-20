"""add agent_runs

Revision ID: f7d1a4c96e28
Revises: e5b9c2a41f76
Create Date: 2026-07-19 17:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'f7d1a4c96e28'
down_revision = 'e5b9c2a41f76'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_runs',
        sa.Column('owner_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=True),
        sa.Column('agent_key', sa.String(length=40), nullable=False),
        sa.Column('objective', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='queued'),
        sa.Column('reasoning_log_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_runs_owner_id', 'agent_runs', ['owner_id'])


def downgrade() -> None:
    op.drop_index('ix_agent_runs_owner_id', table_name='agent_runs')
    op.drop_table('agent_runs')
