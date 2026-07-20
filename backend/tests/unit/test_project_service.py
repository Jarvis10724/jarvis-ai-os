"""
Unit coverage for app.core.project_service — the shared-Project funnel.

Exercises get-or-create default idempotency, timeline event recording, and the
nine-bucket overview aggregation directly against the test DB session (no HTTP),
plus the project_id filters added to approvals and memory search.
"""
import json
import uuid

import pytest

from app.core import capability_service, memory_service, project_service
from app.db.models.capability import ApprovalRequest
from app.db.models.memory import MemoryEntry
from app.db.models.workspace_session import WorkspaceSession
from app.db.session import SessionLocal


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _owner() -> str:
    return f"user-{uuid.uuid4().hex[:8]}"


def test_get_or_create_default_project_is_idempotent(db):
    owner = _owner()
    company = f"co-{uuid.uuid4().hex[:8]}"

    p1 = project_service.get_or_create_default_project(db, owner_id=owner, company_id=company)
    p2 = project_service.get_or_create_default_project(db, owner_id=owner, company_id=company)

    assert p1.id == p2.id
    assert p1.is_default is True
    assert p1.company_id == company


def test_default_project_is_per_company_and_per_client(db):
    owner = _owner()
    a, b = f"co-{uuid.uuid4().hex[:6]}", f"co-{uuid.uuid4().hex[:6]}"

    pa = project_service.get_or_create_default_project(db, owner_id=owner, company_id=a)
    pb = project_service.get_or_create_default_project(db, owner_id=owner, company_id=b)
    # A client build under company A gets its OWN default, separate from A's.
    pc = project_service.get_or_create_default_project(
        db, owner_id=owner, company_id=a, client_id=f"cl-{uuid.uuid4().hex[:6]}"
    )

    assert len({pa.id, pb.id, pc.id}) == 3


def test_record_event_and_overview_aggregates_buckets(db):
    owner = _owner()
    company = f"co-{uuid.uuid4().hex[:8]}"
    project = project_service.get_or_create_default_project(db, owner_id=owner, company_id=company)

    # A session carrying files, an image, and research state → files/images/
    # components/research/conversations buckets.
    state = {
        "files": [{"path": "app.py", "language": "python", "content": "x=1"}],
        "components": {"files": [{"path": "Hero.jsx", "language": "jsx", "description": "hero"}]},
        "images": [{"id": "img1", "name": "Logo", "data_url": "data:image/png;base64,ZmFrZQ==", "status": "generated"}],
        "sources": [{"id": "s1", "title": "Src"}],
        "report": "A findings report.",
    }
    db.add(WorkspaceSession(
        owner_id=owner, company_id=company, action="web_builder", title="Build",
        project_id=project.id, status="active",
        messages_json=json.dumps([{"role": "user", "content": "hi"}]),
        # Same id as the state image — the real generate_image flow stores both
        # under one id, so the overview must dedupe them into a single image.
        artifacts_json=json.dumps([{"id": "img1", "kind": "image", "title": "Mark", "content": "data:image/png;base64,ZmFrZQ=="}]),
        state_json=json.dumps(state),
    ))
    db.commit()

    project_service.record_project_event(
        db, project=project, owner_id=owner, kind="note", title="Kickoff note"
    )

    ov = project_service.build_project_overview(db, project)
    c = ov["counts"]
    assert c["conversations"] == 1
    assert c["files"] >= 2  # state file + component file
    assert c["images"] == 1  # deduped state image vs artifact
    assert c["components"] == 1
    assert c["research"] == 1
    assert c["timeline"] >= 1
    assert ov["research"][0]["has_report"] is True


def test_list_approvals_project_filter(db):
    owner = _owner()
    company = f"co-{uuid.uuid4().hex[:8]}"
    p1 = project_service.get_or_create_default_project(db, owner_id=owner, company_id=company)
    other = project_service.get_or_create_default_project(
        db, owner_id=owner, company_id=f"co-{uuid.uuid4().hex[:6]}"
    )

    db.add(ApprovalRequest(
        owner_id=owner, company_id=company, project_id=p1.id,
        capability_name="gmail", action_type="send_email", payload_json="{}", status="pending",
    ))
    db.add(ApprovalRequest(
        owner_id=owner, company_id=company, project_id=other.id,
        capability_name="gmail", action_type="send_email", payload_json="{}", status="pending",
    ))
    db.commit()

    scoped = capability_service.list_approvals(db, owner_id=owner, company_id="any", project_id=p1.id)
    assert len(scoped) == 1
    assert scoped[0]["project_id"] == p1.id


@pytest.mark.asyncio
async def test_search_memory_project_filter(db):
    owner = _owner()
    company = f"co-{uuid.uuid4().hex[:8]}"
    p1 = project_service.get_or_create_default_project(db, owner_id=owner, company_id=company)

    db.add(MemoryEntry(
        owner_id=owner, company_id=company, project_id=p1.id, scope="project",
        kind="decision", title="In project", content="scoped to project",
    ))
    db.add(MemoryEntry(
        owner_id=owner, company_id=company, project_id=None, scope="company",
        kind="decision", title="Company wide", content="not project scoped",
    ))
    db.commit()

    results = await memory_service.search_memory(
        db, owner_id=owner, query="", company_id="any", project_id=p1.id
    )
    titles = {r["title"] for r in results}
    assert "In project" in titles
    assert "Company wide" not in titles
