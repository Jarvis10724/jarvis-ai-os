"""add memory confidence and audit log

Revision ID: a9d2e5f7c3b8
Revises: f3c8b6a1d4e2
Create Date: 2026-07-19 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a9d2e5f7c3b8'
down_revision = 'f3c8b6a1d4e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('memory_entries') as batch_op:
        batch_op.add_column(sa.Column('confidence', sa.Float(), nullable=True))

    op.create_table('memory_audit_log',
    sa.Column('memory_entry_id', sa.String(), nullable=False),
    sa.Column('owner_id', sa.String(), nullable=False),
    sa.Column('action', sa.String(length=20), nullable=False),
    sa.Column('before_json', sa.Text(), nullable=True),
    sa.Column('after_json', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_memory_audit_log_memory_entry_id', 'memory_audit_log', ['memory_entry_id'])
    op.create_index('ix_memory_audit_log_owner_id', 'memory_audit_log', ['owner_id'])


def downgrade() -> None:
    op.drop_index('ix_memory_audit_log_owner_id', table_name='memory_audit_log')
    op.drop_index('ix_memory_audit_log_memory_entry_id', table_name='memory_audit_log')
    op.drop_table('memory_audit_log')

    with op.batch_alter_table('memory_entries') as batch_op:
        batch_op.drop_column('confidence')
