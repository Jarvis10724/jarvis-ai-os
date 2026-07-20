"""add oauth_states table

Revision ID: c7f2a9d1e5b3
Revises: b1e4f6a8c3d0
Create Date: 2026-07-24 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c7f2a9d1e5b3'
down_revision = 'b1e4f6a8c3d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('oauth_states',
    sa.Column('state', sa.String(length=128), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('company_id', sa.String(), nullable=True),
    sa.Column('capability_name', sa.String(length=50), nullable=False),
    sa.Column('redirect_uri', sa.String(length=500), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('state')
    )
    op.create_index('ix_oauth_states_state', 'oauth_states', ['state'])
    op.create_index('ix_oauth_states_user_id', 'oauth_states', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_oauth_states_user_id', table_name='oauth_states')
    op.drop_index('ix_oauth_states_state', table_name='oauth_states')
    op.drop_table('oauth_states')
