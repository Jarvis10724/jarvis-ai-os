"""
Projects — the durable, company-scoped shared container every Quick Action
attaches to. See app.db.models.project.Project and app.core.project_service.

This exposes the company-scoped list, the get-or-create default project, the
aggregated overview (the nine buckets a project contains), and the timeline.
The older project-nested Task endpoints are kept unchanged for plugin-run
tasks.
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import project_service
from app.db.models.company import Company
from app.db.models.project import Project
from app.db.models.project_event import ProjectEvent
from app.db.models.task import Task
from app.db.session import get_db
from app.exceptions import NotFoundError

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    company_id: str | None = None
    client_id: str | None = None


class ProjectRead(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    company_id: str | None
    client_id: str | None
    is_default: bool

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    plugin_name: str | None = None


class TaskRead(BaseModel):
    id: str
    title: str
    description: str | None
    status: str
    plugin_name: str | None

    model_config = {"from_attributes": True}


def _assert_company(db: Session, company_id: str | None, owner_id: str) -> None:
    if company_id is None:
        return
    exists = db.query(Company.id).filter(Company.id == company_id, Company.owner_id == owner_id).first()
    if not exists:
        raise NotFoundError(f"Company '{company_id}' not found")


@router.get("", response_model=list[ProjectRead])
def list_projects(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = None,
):
    """List the user's projects, optionally scoped to a business. Pass
    `company_id=none` for account-wide (null-company) projects, mirroring the
    workspaces/clients sentinel."""
    q = db.query(Project).filter(Project.owner_id == current_user.id)
    if company_id == "none":
        q = q.filter(Project.company_id.is_(None))
    elif company_id:
        q = q.filter(Project.company_id == company_id)
    return q.order_by(Project.is_default.desc(), Project.created_at.desc()).all()


@router.get("/default", response_model=ProjectRead)
def get_default_project(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = None,
    client_id: str | None = None,
):
    """Get (or create) the default project for a business — the one Quick
    Actions attach to when none is specified."""
    resolved = None if company_id in (None, "none") else company_id
    _assert_company(db, resolved, current_user.id)
    return project_service.get_or_create_default_project(
        db, owner_id=current_user.id, company_id=resolved, client_id=client_id
    )


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    _assert_company(db, payload.company_id, current_user.id)
    project = Project(
        owner_id=current_user.id,
        name=payload.name,
        description=payload.description,
        company_id=payload.company_id,
        client_id=payload.client_id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _get_owned_project(project_id: str, current_user, db: Session) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.owner_id == current_user.id)
        .first()
    )
    if not project:
        raise NotFoundError(f"Project '{project_id}' not found")
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    return _get_owned_project(project_id, current_user, db)


@router.get("/{project_id}/overview")
def get_project_overview(project_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    """The nine buckets this project contains — Conversations, Files, Images,
    Components, Research, Tasks, Approvals, Timeline, Memory."""
    project = _get_owned_project(project_id, current_user, db)
    return project_service.build_project_overview(db, project)


@router.get("/{project_id}/timeline")
def get_project_timeline(
    project_id: str, current_user: CurrentUser, db: Session = Depends(get_db), limit: int = 100
):
    project = _get_owned_project(project_id, current_user, db)
    events = (
        db.query(ProjectEvent)
        .filter(ProjectEvent.project_id == project.id)
        .order_by(ProjectEvent.created_at.desc())
        .limit(min(limit, 500))
        .all()
    )
    return [project_service.serialize_event(e) for e in events]


@router.get("/{project_id}/tasks", response_model=list[TaskRead])
def list_tasks(project_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    project = _get_owned_project(project_id, current_user, db)
    return project.tasks


@router.post("/{project_id}/tasks", response_model=TaskRead, status_code=201)
def create_task(
    project_id: str, payload: TaskCreate, current_user: CurrentUser, db: Session = Depends(get_db)
):
    project = _get_owned_project(project_id, current_user, db)
    task = Task(
        project_id=project.id,
        title=payload.title,
        description=payload.description,
        plugin_name=payload.plugin_name,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
