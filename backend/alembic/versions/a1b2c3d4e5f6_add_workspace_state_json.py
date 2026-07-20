"""add state_json to workspace_sessions

Adds the structured, action-specific workspace state column that turns each
Quick Action into a full studio (sitemap/copy/design, brief/concepts/revisions,
research plan/sources/citations, automation trigger/actions/conditions, ...).
Additive only — existing messages_json/artifacts_json data is untouched.

Revision ID: a1b2c3d4e5f6
Revises: f7d1a4c96e28
Create Date: 2026-07-19 17:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'f7d1a4c96e28'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'workspace_sessions',
        sa.Column('state_json', sa.Text(), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    op.drop_column('workspace_sessions', 'state_json')
