"""scope tasks to company and add board fields

Revision ID: d8a3c5f19e47
Revises: c7f2a9d1e5b3
Create Date: 2026-07-19 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'd8a3c5f19e47'
down_revision = 'c7f2a9d1e5b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('company_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('owner_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('division', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('assignee', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('due_date', sa.String(length=20), nullable=True))
        batch_op.alter_column('project_id', existing_type=sa.String(), nullable=True)
        batch_op.alter_column('status', existing_type=sa.String(length=50), server_default='backlog')
        batch_op.create_foreign_key('fk_tasks_company_id', 'companies', ['company_id'], ['id'])
        batch_op.create_foreign_key('fk_tasks_owner_id', 'users', ['owner_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tasks_owner_id', type_='foreignkey')
        batch_op.drop_constraint('fk_tasks_company_id', type_='foreignkey')
        batch_op.alter_column('status', existing_type=sa.String(length=50), server_default='todo')
        batch_op.alter_column('project_id', existing_type=sa.String(), nullable=False)
        batch_op.drop_column('due_date')
        batch_op.drop_column('assignee')
        batch_op.drop_column('division')
        batch_op.drop_column('owner_id')
        batch_op.drop_column('company_id')
