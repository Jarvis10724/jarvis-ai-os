"""
project_service — the single funnel for the shared Project system.

A Project is the durable, company-scoped container every Quick Action attaches
to (see app.db.models.project.Project). Nothing outside this module should
create default projects, write timeline events, or reassemble a project's
aggregated view — every caller goes through here, exactly like memory goes
through memory_service and external actions go through capability_service.

Three responsibilities:
  - get_or_create_default_project: resolve the one default project a Quick
    Action attaches to for a given (owner, company[, client]).
  - record_project_event: append one row to the project Timeline.
  - build_project_overview: aggregate the nine buckets (Conversations, Files,
    Images, Components, Research, Tasks, Approvals, Timeline, Memory) a Project
    "contains" from the sessions/tasks/approvals/memory/events pointing at it.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core import workspace_state as ws
from app.db.models.capability import ApprovalRequest
from app.db.models.client import Client
from app.db.models.company import Company
from app.db.models.memory import MemoryEntry
from app.db.models.project import Project
from app.db.models.project_event import ProjectEvent
from app.db.models.task import Task
from app.db.models.workspace_session import WorkspaceSession

# Artifact kinds that count as generated "files" (everything that isn't an
# image). Images get their own bucket.
_FILE_ARTIFACT_KINDS = {"file", "code", "document", "text", "markdown"}


def get_or_create_default_project(
    db: Session,
    *,
    owner_id: str,
    company_id: str | None,
    client_id: str | None = None,
    commit: bool = True,
) -> Project:
    """Return the default Project for this (owner, company[, client]),
    creating it if it doesn't exist yet. This is what a Quick Action attaches
    to when the caller didn't pick a specific project. Idempotent — repeated
    calls return the same row."""
    q = (
        db.query(Project)
        .filter(
            Project.owner_id == owner_id,
            Project.is_default.is_(True),
        )
    )
    q = q.filter(Project.company_id == company_id) if company_id else q.filter(Project.company_id.is_(None))
    q = q.filter(Project.client_id == client_id) if client_id else q.filter(Project.client_id.is_(None))
    existing = q.order_by(Project.created_at.asc()).first()
    if existing:
        return existing

    project = Project(
        owner_id=owner_id,
        company_id=company_id,
        client_id=client_id,
        name=_default_project_name(db, company_id=company_id, client_id=client_id),
        description="Shared workspace — everything Jarvis builds for this "
        + ("client" if client_id else "business") + " lives here.",
        status="active",
        is_default=True,
    )
    db.add(project)
    if commit:
        db.commit()
        db.refresh(project)
    else:
        db.flush()
    return project


def _default_project_name(db: Session, *, company_id: str | None, client_id: str | None) -> str:
    if client_id:
        name = db.query(Client.name).filter(Client.id == client_id).scalar()
        return (f"{name} — Workspace" if name else "Client Workspace")[:255]
    if company_id:
        name = db.query(Company.name).filter(Company.id == company_id).scalar()
        return (name or "Workspace")[:255]
    return "My Workspace"


def record_project_event(
    db: Session,
    *,
    project: Project,
    owner_id: str,
    kind: str,
    title: str,
    source: str = "jarvis",
    detail: str | None = None,
    ref_id: str | None = None,
    commit: bool = True,
) -> ProjectEvent:
    """Append one Timeline row for a project. `kind`/`source` are free-form
    (see PROJECT_EVENT_KINDS for the documented set)."""
    event = ProjectEvent(
        project_id=project.id,
        company_id=project.company_id,
        owner_id=owner_id,
        kind=kind,
        title=title[:500],
        detail=detail,
        source=source,
        ref_id=ref_id,
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    else:
        db.flush()
    return event


def build_project_overview(db: Session, project: Project, *, limit: int = 100) -> dict:
    """Assemble the nine buckets a Project contains from everything pointing at
    it. Reads across attached WorkspaceSessions' JSON blobs — fine at the scale
    one business generates (same assumption as memory's brute-force search)."""
    from app.core.workspace_actions import get_action  # local: avoids cycle

    sessions = (
        db.query(WorkspaceSession)
        .filter(WorkspaceSession.project_id == project.id)
        .order_by(WorkspaceSession.updated_at.desc())
        .all()
    )

    conversations: list[dict] = []
    files: list[dict] = []
    images: list[dict] = []
    components: list[dict] = []
    research: list[dict] = []

    for s in sessions:
        action = get_action(s.action)
        label = action.label if action else s.action
        messages = ws.load_json(s.messages_json, [])
        state = ws.load_json(s.state_json, {})
        artifacts = ws.load_json(s.artifacts_json, [])

        conversations.append({
            "session_id": s.id,
            "action": s.action,
            "action_label": label,
            "title": s.title,
            "message_count": len(messages),
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        })

        # Files — code_writer state.files, web_builder components.files, and any
        # non-image artifact saved to the session.
        for f in _as_list(state.get("files")):
            if isinstance(f, dict) and f.get("path"):
                files.append({
                    "session_id": s.id, "action": s.action,
                    "path": f.get("path"), "language": f.get("language"), "source": "state",
                })
        comp_obj = state.get("components")
        comp_files = comp_obj.get("files") if isinstance(comp_obj, dict) else None
        for cf in _as_list(comp_files):
            if isinstance(cf, dict) and cf.get("path"):
                item = {
                    "session_id": s.id, "path": cf.get("path"),
                    "language": cf.get("language"), "description": cf.get("description"),
                }
                components.append(item)
                files.append({
                    "session_id": s.id, "action": s.action,
                    "path": cf.get("path"), "language": cf.get("language"), "source": "component",
                })
        for a in artifacts:
            if isinstance(a, dict) and a.get("kind") in _FILE_ARTIFACT_KINDS:
                files.append({
                    "session_id": s.id, "action": s.action,
                    "path": a.get("title"), "artifact_id": a.get("id"),
                    "kind": a.get("kind"), "source": "artifact",
                })

        # Images — state.images (web_builder / logo) + image artifacts.
        for im in _as_list(state.get("images")):
            if isinstance(im, dict):
                images.append({
                    "session_id": s.id, "action": s.action,
                    "id": im.get("id"), "name": im.get("name") or im.get("alt") or im.get("role"),
                    "data_url": im.get("data_url"), "status": im.get("status"),
                })
        for a in artifacts:
            if isinstance(a, dict) and a.get("kind") == "image":
                if not any(i.get("id") == a.get("id") for i in images):
                    images.append({
                        "session_id": s.id, "action": s.action,
                        "id": a.get("id"), "name": a.get("title"),
                        "data_url": a.get("content"), "status": "generated",
                    })

        # Research — deep_research sources/citations/report.
        srcs = _as_list(state.get("sources"))
        cites = _as_list(state.get("citations"))
        report = state.get("report")
        if srcs or cites or report:
            research.append({
                "session_id": s.id, "title": s.title,
                "source_count": len(srcs), "citation_count": len(cites),
                "has_report": bool(report),
                "report_excerpt": (report[:500] if isinstance(report, str) else None),
            })

    tasks = (
        db.query(Task)
        .filter(Task.project_id == project.id)
        .order_by(Task.created_at.asc())
        .all()
    )
    approvals = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.project_id == project.id)
        .order_by(ApprovalRequest.created_at.desc())
        .all()
    )
    memory = (
        db.query(MemoryEntry)
        .filter(MemoryEntry.project_id == project.id)
        .order_by(MemoryEntry.created_at.desc())
        .all()
    )
    timeline = (
        db.query(ProjectEvent)
        .filter(ProjectEvent.project_id == project.id)
        .order_by(ProjectEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "project": serialize_project(project),
        "counts": {
            "conversations": len(conversations),
            "files": len(files),
            "images": len(images),
            "components": len(components),
            "research": len(research),
            "tasks": len(tasks),
            "approvals": len(approvals),
            "timeline": len(timeline),
            "memory": len(memory),
        },
        "conversations": conversations[:limit],
        "files": files[:limit],
        "images": images[:limit],
        "components": components[:limit],
        "research": research[:limit],
        "tasks": [
            {"id": t.id, "title": t.title, "status": t.status, "due_date": t.due_date}
            for t in tasks[:limit]
        ],
        "approvals": [
            {
                "id": a.id, "capability_name": a.capability_name, "action_type": a.action_type,
                "status": a.status, "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in approvals[:limit]
        ],
        "memory": [
            {
                "id": m.id, "kind": m.kind, "title": m.title, "scope": m.scope,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memory[:limit]
        ],
        "timeline": [serialize_event(e) for e in timeline],
    }


def serialize_project(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "status": p.status,
        "company_id": p.company_id,
        "client_id": p.client_id,
        "is_default": bool(p.is_default),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def serialize_event(e: ProjectEvent) -> dict:
    return {
        "id": e.id,
        "kind": e.kind,
        "title": e.title,
        "detail": e.detail,
        "source": e.source,
        "ref_id": e.ref_id,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _as_list(value) -> list:
    return value if isinstance(value, list) else []
