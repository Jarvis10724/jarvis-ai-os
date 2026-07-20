"""add clients + client_id on workspace_sessions and projects

Supports the Website Builder's "Build Client Website" mode: a Client entity
(scoped to owner + company) with projects/sessions kept separate from the
company's own work.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-20 20:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clients_owner_id", "clients", ["owner_id"])
    with op.batch_alter_table("workspace_sessions") as batch:
        batch.add_column(sa.Column("client_id", sa.String(), nullable=True))
        batch.create_foreign_key("fk_ws_client", "clients", ["client_id"], ["id"])
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("client_id", sa.String(), nullable=True))
        batch.create_foreign_key("fk_project_client", "clients", ["client_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("fk_project_client", type_="foreignkey")
        batch.drop_column("client_id")
    with op.batch_alter_table("workspace_sessions") as batch:
        batch.drop_constraint("fk_ws_client", type_="foreignkey")
        batch.drop_column("client_id")
    op.drop_index("ix_clients_owner_id", table_name="clients")
    op.drop_table("clients")
