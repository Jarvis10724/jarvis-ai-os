"""add capability framework (config, approvals, audit log, scheduled jobs)

Revision ID: b1e4f6a8c3d0
Revises: a9d2e5f7c3b8
Create Date: 2026-07-17 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b1e4f6a8c3d0'
down_revision = 'a9d2e5f7c3b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('capability_configs',
    sa.Column('owner_id', sa.String(), nullable=False),
    sa.Column('company_id', sa.String(), nullable=True),
    sa.Column('capability_name', sa.String(length=50), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('permissions_json', sa.Text(), nullable=True),
    sa.Column('config_json', sa.Text(), nullable=True),
    sa.Column('health_status', sa.String(length=20), nullable=False),
    sa.Column('health_message', sa.Text(), nullable=True),
    sa.Column('last_health_check_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_capability_configs_owner_id', 'capability_configs', ['owner_id'])
    op.create_index('ix_capability_configs_company_id', 'capability_configs', ['company_id'])
    op.create_index('ix_capability_configs_capability_name', 'capability_configs', ['capability_name'])

    op.create_table('approval_requests',
    sa.Column('owner_id', sa.String(), nullable=False),
    sa.Column('company_id', sa.String(), nullable=True),
    sa.Column('capability_name', sa.String(length=50), nullable=False),
    sa.Column('action_type', sa.String(length=50), nullable=False),
    sa.Column('payload_json', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('requested_by', sa.String(), nullable=True),
    sa.Column('decided_by', sa.String(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_approval_requests_owner_id', 'approval_requests', ['owner_id'])
    op.create_index('ix_approval_requests_company_id', 'approval_requests', ['company_id'])
    op.create_index('ix_approval_requests_capability_name', 'approval_requests', ['capability_name'])
    op.create_index('ix_approval_requests_status', 'approval_requests', ['status'])

    op.create_table('capability_audit_log',
    sa.Column('owner_id', sa.String(), nullable=False),
    sa.Column('company_id', sa.String(), nullable=True),
    sa.Column('capability_name', sa.String(length=50), nullable=False),
    sa.Column('approval_request_id', sa.String(), nullable=True),
    sa.Column('action', sa.String(length=30), nullable=False),
    sa.Column('before_json', sa.Text(), nullable=True),
    sa.Column('after_json', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_capability_audit_log_owner_id', 'capability_audit_log', ['owner_id'])
    op.create_index('ix_capability_audit_log_company_id', 'capability_audit_log', ['company_id'])
    op.create_index('ix_capability_audit_log_capability_name', 'capability_audit_log', ['capability_name'])
    op.create_index('ix_capability_audit_log_approval_request_id', 'capability_audit_log', ['approval_request_id'])

    op.create_table('scheduled_jobs',
    sa.Column('owner_id', sa.String(), nullable=False),
    sa.Column('company_id', sa.String(), nullable=True),
    sa.Column('capability_name', sa.String(length=50), nullable=False),
    sa.Column('action_type', sa.String(length=50), nullable=False),
    sa.Column('payload_json', sa.Text(), nullable=False),
    sa.Column('schedule_cron', sa.String(length=100), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scheduled_jobs_owner_id', 'scheduled_jobs', ['owner_id'])
    op.create_index('ix_scheduled_jobs_company_id', 'scheduled_jobs', ['company_id'])
    op.create_index('ix_scheduled_jobs_capability_name', 'scheduled_jobs', ['capability_name'])


def downgrade() -> None:
    op.drop_index('ix_scheduled_jobs_capability_name', table_name='scheduled_jobs')
    op.drop_index('ix_scheduled_jobs_company_id', table_name='scheduled_jobs')
    op.drop_index('ix_scheduled_jobs_owner_id', table_name='scheduled_jobs')
    op.drop_table('scheduled_jobs')

    op.drop_index('ix_capability_audit_log_approval_request_id', table_name='capability_audit_log')
    op.drop_index('ix_capability_audit_log_capability_name', table_name='capability_audit_log')
    op.drop_index('ix_capability_audit_log_company_id', table_name='capability_audit_log')
    op.drop_index('ix_capability_audit_log_owner_id', table_name='capability_audit_log')
    op.drop_table('capability_audit_log')

    op.drop_index('ix_approval_requests_status', table_name='approval_requests')
    op.drop_index('ix_approval_requests_capability_name', table_name='approval_requests')
    op.drop_index('ix_approval_requests_company_id', table_name='approval_requests')
    op.drop_index('ix_approval_requests_owner_id', table_name='approval_requests')
    op.drop_table('approval_requests')

    op.drop_index('ix_capability_configs_capability_name', table_name='capability_configs')
    op.drop_index('ix_capability_configs_company_id', table_name='capability_configs')
    op.drop_index('ix_capability_configs_owner_id', table_name='capability_configs')
    op.drop_table('capability_configs')
