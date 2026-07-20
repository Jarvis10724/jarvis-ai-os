"""add scope and project_id to memory_entries

Revision ID: f3c8b6a1d4e2
Revises: e7a1f4c9b210
Create Date: 2026-07-18 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'f3c8b6a1d4e2'
down_revision = 'e7a1f4c9b210'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('memory_entries') as batch_op:
        batch_op.add_column(sa.Column('scope', sa.String(length=20), nullable=False, server_default='organization'))
        batch_op.add_column(sa.Column('project_id', sa.String(), nullable=True))
        batch_op.create_foreign_key('fk_memory_entries_project_id', 'projects', ['project_id'], ['id'])

    # Backfill: every pre-existing row that already had a company_id was
    # implicitly company-scoped under the old binary (company vs global)
    # model — everything else defaults to 'organization' via the column's
    # server_default above, since that was the closest existing equivalent
    # ("global/personal memory not tied to one company").
    op.execute("UPDATE memory_entries SET scope = 'company' WHERE company_id IS NOT NULL")

    op.create_index('ix_memory_entries_scope', 'memory_entries', ['scope'])
    op.create_index('ix_memory_entries_project_id', 'memory_entries', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_memory_entries_project_id', table_name='memory_entries')
    op.drop_index('ix_memory_entries_scope', table_name='memory_entries')
    with op.batch_alter_table('memory_entries') as batch_op:
        batch_op.drop_constraint('fk_memory_entries_project_id', type_='foreignkey')
        batch_op.drop_column('project_id')
        batch_op.drop_column('scope')
