"""
Integration coverage for the shared Project system.

Verifies the core behavioural contract: every Quick Action in a business
attaches to the SAME shared (default) Project instead of minting its own,
switching businesses re-scopes to a different default with isolation intact,
an explicit project attaches there, and the project overview aggregates the
nine buckets. Also exercises the migration's consolidation routine directly.
"""
import importlib.util
import json
import uuid
from pathlib import Path

from app.core import project_service
from app.db.models.project import Project
from app.db.models.task import Task
from app.db.models.workspace_session import WorkspaceSession
from app.db.session import SessionLocal

API = "/api/v1"


def _register_and_login(client, email: str, password: str = "supersecret123") -> dict:
    client.post(f"{API}/auth/register", json={"email": email, "password": password})
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_company(client, headers: dict, name: str) -> str:
    resp = client.post(f"{API}/companies", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_two_quick_actions_share_one_default_project(client):
    headers = _register_and_login(client, "ps-share@example.com")
    company = _create_company(client, headers, "SharedCo")

    a = client.post(f"{API}/workspaces", json={"action": "web_builder", "company_id": company}, headers=headers).json()
    b = client.post(f"{API}/workspaces", json={"action": "logo_design", "company_id": company}, headers=headers).json()

    # Both Quick Actions rolled into the SAME shared project — not two.
    assert a["project_id"] == b["project_id"]

    projects = client.get(f"{API}/projects?company_id={company}", headers=headers).json()
    assert len(projects) == 1
    assert projects[0]["is_default"] is True
    assert projects[0]["id"] == a["project_id"]


def test_default_project_differs_per_business_and_isolates(client):
    headers = _register_and_login(client, "ps-iso@example.com")
    a = _create_company(client, headers, "BizA")
    b = _create_company(client, headers, "BizB")

    sa = client.post(f"{API}/workspaces", json={"action": "web_builder", "company_id": a}, headers=headers).json()
    sb = client.post(f"{API}/workspaces", json={"action": "web_builder", "company_id": b}, headers=headers).json()
    assert sa["project_id"] != sb["project_id"]

    # Each business's project list is scoped to it.
    a_projects = client.get(f"{API}/projects?company_id={a}", headers=headers).json()
    b_projects = client.get(f"{API}/projects?company_id={b}", headers=headers).json()
    assert {p["id"] for p in a_projects}.isdisjoint({p["id"] for p in b_projects})


def test_default_project_endpoint_is_idempotent(client):
    headers = _register_and_login(client, "ps-default@example.com")
    company = _create_company(client, headers, "DefCo")
    p1 = client.get(f"{API}/projects/default?company_id={company}", headers=headers).json()
    p2 = client.get(f"{API}/projects/default?company_id={company}", headers=headers).json()
    assert p1["id"] == p2["id"] and p1["is_default"] is True


def test_explicit_project_id_attaches_there(client):
    headers = _register_and_login(client, "ps-explicit@example.com")
    company = _create_company(client, headers, "ExplicitCo")
    proj = client.post(
        f"{API}/projects", json={"name": "Campaign Q3", "company_id": company}, headers=headers
    ).json()

    s = client.post(
        f"{API}/workspaces",
        json={"action": "deep_research", "company_id": company, "project_id": proj["id"]},
        headers=headers,
    ).json()
    assert s["project_id"] == proj["id"]


def test_project_overview_aggregates_buckets(client):
    headers = _register_and_login(client, "ps-overview@example.com")
    company = _create_company(client, headers, "OverviewCo")
    s = client.post(
        f"{API}/workspaces", json={"action": "code_writer", "company_id": company}, headers=headers
    ).json()
    project_id = s["project_id"]

    # Save a file artifact + attach a task.
    client.post(
        f"{API}/workspaces/{s['id']}/artifacts",
        json={"title": "main.py", "content": "print(1)", "kind": "code", "stage": "files"},
        headers=headers,
    )
    client.post(f"{API}/workspaces/{s['id']}/tasks", json={"title": "Ship it"}, headers=headers)

    ov = client.get(f"{API}/projects/{project_id}/overview", headers=headers).json()
    assert ov["counts"]["conversations"] == 1
    assert ov["counts"]["files"] >= 1
    assert ov["counts"]["tasks"] >= 2  # kick-off + attached
    # Timeline captured session creation + the artifact save + task add.
    kinds = {e["kind"] for e in ov["timeline"]}
    assert "session_created" in kinds
    assert {"artifact_saved", "task_created"} & kinds


def test_project_timeline_endpoint(client):
    headers = _register_and_login(client, "ps-timeline@example.com")
    company = _create_company(client, headers, "TimelineCo")
    s = client.post(
        f"{API}/workspaces", json={"action": "automation", "company_id": company}, headers=headers
    ).json()
    tl = client.get(f"{API}/projects/{s['project_id']}/timeline", headers=headers).json()
    assert any(e["kind"] == "session_created" for e in tl)


def test_project_overview_not_owned_404(client):
    headers = _register_and_login(client, "ps-owner@example.com")
    company = _create_company(client, headers, "OwnerCo")
    s = client.post(
        f"{API}/workspaces", json={"action": "logo_design", "company_id": company}, headers=headers
    ).json()
    intruder = _register_and_login(client, "ps-intruder@example.com")
    assert client.get(f"{API}/projects/{s['project_id']}/overview", headers=intruder).status_code == 404


def test_migration_consolidation_merges_throwaway_projects():
    """Load the migration module and run its consolidation routine against a
    seeded 'old world' (several per-session throwaway projects for one company)
    — sessions/tasks re-point to a single default and the empties are gone."""
    spec_path = (
        Path(__file__).resolve().parents[2]
        / "alembic" / "versions" / "d1f2a3b4c5e6_add_shared_project_system.py"
    )
    spec = importlib.util.spec_from_file_location("mig_consolidate", spec_path)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)

    db = SessionLocal()
    owner = f"user-{uuid.uuid4().hex[:8]}"
    company = f"co-{uuid.uuid4().hex[:8]}"
    try:
        # Two throwaway projects, each with its own session + task (the pre-shared
        # world where every Quick Action minted a project). company_id starts
        # NULL — exactly like pre-migration rows; the routine backfills it.
        proj_ids = []
        for i in range(2):
            p = Project(owner_id=owner, name=f"Studio: thing {i}", status="active")
            db.add(p)
            db.flush()
            proj_ids.append(p.id)
            db.add(WorkspaceSession(
                owner_id=owner, company_id=company, action="web_builder",
                title=f"S{i}", project_id=p.id, status="active",
                messages_json="[]", artifacts_json="[]", state_json="{}",
            ))
            db.add(Task(owner_id=owner, company_id=company, project_id=p.id, title=f"t{i}", status="backlog"))
        db.commit()

        # op.get_bind() yields a Connection in a real migration; mirror that
        # here (SQLAlchemy 2.0 Engine has no .execute()).
        mig._consolidate(db.connection())
        db.commit()
        db.expire_all()

        # Exactly one project remains for the company, marked default.
        remaining = db.query(Project).filter(Project.company_id == company).all()
        assert len(remaining) == 1
        default_id = remaining[0].id
        assert remaining[0].is_default is True

        # Both old project ids collapsed; every session/task re-pointed.
        surviving_ids = {p.id for p in db.query(Project).filter(Project.id.in_(proj_ids)).all()}
        assert surviving_ids <= {default_id}
        assert db.query(WorkspaceSession).filter(
            WorkspaceSession.company_id == company,
            WorkspaceSession.project_id != default_id,
        ).count() == 0
        assert db.query(Task).filter(
            Task.company_id == company, Task.project_id != default_id
        ).count() == 0
    finally:
        # Clean up so the shared test DB stays tidy for other tests.
        db.query(WorkspaceSession).filter(WorkspaceSession.company_id == company).delete()
        db.query(Task).filter(Task.company_id == company).delete()
        db.query(Project).filter(Project.company_id == company).delete()
        db.commit()
        db.close()
