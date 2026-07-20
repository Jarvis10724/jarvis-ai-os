"""shared project system: company-scoped projects, project timeline,
project-scoped approvals, and consolidation of throwaway per-session projects

Turns Project from a throwaway container (one auto-created per Quick-Action
session) into a durable, company-scoped shared container that all Quick
Actions attach to.

Schema:
  - projects.company_id      -> scope projects to a business (Company)
  - projects.is_default      -> the per-(company[,client]) default project
  - approval_requests.project_id -> roll approvals up to a project
  - project_events (new)     -> the Project Timeline

Data (consolidation, idempotent + guarded):
  Backfills projects.company_id from each project's attached workspace
  session, then merges every business's per-session throwaway projects into a
  single default project per (company, client): re-points workspace_sessions,
  tasks, memory_entries, and agent_runs, then deletes the emptied projects.

NOTE: downgrade drops the new schema but CANNOT un-merge consolidated
projects — the pre-consolidation project rows are gone. Back up data/jarvis.db
before upgrading (the runbook does this).

Revision ID: d1f2a3b4c5e6
Revises: b2c3d4e5f6a7
Create Date: 2026-07-20 22:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "d1f2a3b4c5e6"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- schema ---------------------------------------------------------
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("company_id", sa.String(), nullable=True))
        batch.add_column(
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0"))
        )
        batch.create_foreign_key("fk_project_company", "companies", ["company_id"], ["id"])
    op.create_index("ix_projects_company_id", "projects", ["company_id"])

    with op.batch_alter_table("approval_requests") as batch:
        batch.add_column(sa.Column("project_id", sa.String(), nullable=True))
        batch.create_foreign_key("fk_approval_project", "projects", ["project_id"], ["id"])
    op.create_index("ix_approval_requests_project_id", "approval_requests", ["project_id"])

    op.create_table(
        "project_events",
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=True),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="jarvis"),
        sa.Column("ref_id", sa.String(length=500), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_events_project_id", "project_events", ["project_id"])
    op.create_index("ix_project_events_company_id", "project_events", ["company_id"])
    op.create_index("ix_project_events_owner_id", "project_events", ["owner_id"])

    # --- data: backfill company_id, then consolidate --------------------
    _consolidate(op.get_bind())


def _consolidate(conn) -> None:
    """Backfill projects.company_id from attached sessions, then merge each
    business's per-session throwaway projects into one default project per
    (company_id, client_id). Idempotent: re-running with already-consolidated
    data re-marks the same defaults and re-points nothing new."""
    # 1. Backfill company_id from any attached workspace session.
    conn.execute(sa.text(
        """
        UPDATE projects
           SET company_id = (
               SELECT ws.company_id
                 FROM workspace_sessions ws
                WHERE ws.project_id = projects.id
                  AND ws.company_id IS NOT NULL
                LIMIT 1
           )
         WHERE company_id IS NULL
        """
    ))

    # 2. Group projects that now have a company by (company_id, client_id) and
    #    collapse each group to a single default project. Only projects with a
    #    resolved company_id participate — standalone/null-company projects are
    #    left untouched.
    groups = conn.execute(sa.text(
        """
        SELECT company_id, client_id
          FROM projects
         WHERE company_id IS NOT NULL
         GROUP BY company_id, client_id
        """
    )).fetchall()

    for company_id, client_id in groups:
        client_pred = "client_id = :cid" if client_id is not None else "client_id IS NULL"
        params = {"company": company_id}
        if client_id is not None:
            params["cid"] = client_id

        rows = conn.execute(sa.text(
            f"""
            SELECT id FROM projects
             WHERE company_id = :company AND {client_pred}
             ORDER BY is_default DESC, created_at ASC
            """
        ), params).fetchall()
        ids = [r[0] for r in rows]
        if not ids:
            continue
        default_id = ids[0]
        merged_ids = ids[1:]

        # Name the default readably: company name (or "<client> — Workspace").
        if client_id is not None:
            new_name = conn.execute(
                sa.text("SELECT name FROM clients WHERE id = :id"), {"id": client_id}
            ).scalar()
            new_name = f"{new_name} — Workspace" if new_name else "Client Workspace"
        else:
            new_name = conn.execute(
                sa.text("SELECT name FROM companies WHERE id = :id"), {"id": company_id}
            ).scalar() or "Workspace"

        conn.execute(sa.text(
            "UPDATE projects SET is_default = 1, name = :name, status = 'active' WHERE id = :id"
        ), {"name": new_name[:255], "id": default_id})

        if not merged_ids:
            continue

        placeholders = ", ".join(f":m{i}" for i in range(len(merged_ids)))
        merge_params = {f"m{i}": mid for i, mid in enumerate(merged_ids)}
        merge_params["default"] = default_id

        for table in ("workspace_sessions", "tasks", "memory_entries", "agent_runs"):
            conn.execute(sa.text(
                f"UPDATE {table} SET project_id = :default WHERE project_id IN ({placeholders})"
            ), merge_params)

        # Emptied throwaway projects can now be removed.
        conn.execute(sa.text(
            f"DELETE FROM projects WHERE id IN ({placeholders})"
        ), merge_params)


def downgrade() -> None:
    op.drop_index("ix_project_events_owner_id", table_name="project_events")
    op.drop_index("ix_project_events_company_id", table_name="project_events")
    op.drop_index("ix_project_events_project_id", table_name="project_events")
    op.drop_table("project_events")

    op.drop_index("ix_approval_requests_project_id", table_name="approval_requests")
    with op.batch_alter_table("approval_requests") as batch:
        batch.drop_constraint("fk_approval_project", type_="foreignkey")
        batch.drop_column("project_id")

    op.drop_index("ix_projects_company_id", table_name="projects")
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("fk_project_company", type_="foreignkey")
        batch.drop_column("is_default")
        batch.drop_column("company_id")
