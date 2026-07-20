"""multi-company: add checklists_json to companies, company_id to integration_credentials

Revision ID: a23853679925
Revises: 1cd607497503
Create Date: 2026-07-16 17:41:17.527441
"""
from alembic import op
import sqlalchemy as sa


revision = 'a23853679925'
down_revision = '1cd607497503'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A prior partial run (pre-batch-mode fix) already added both columns
    # directly; only the FK constraint on integration_credentials is missing.
    with op.batch_alter_table('integration_credentials') as batch_op:
        batch_op.create_foreign_key(
            'fk_integration_credentials_company_id', 'companies', ['company_id'], ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table('integration_credentials') as batch_op:
        batch_op.drop_constraint('fk_integration_credentials_company_id', type_='foreignkey')
        batch_op.drop_column('company_id')
    op.drop_column('companies', 'checklists_json')
