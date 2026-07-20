from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.models.project import Project
from app.db.models.task import Task
from app.db.session import get_db
from app.exceptions import NotFoundError

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectRead(BaseModel):
    id: str
    name: str
    description: str | None
    status: str

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


@router.get("", response_model=list[ProjectRead])
def list_projects(current_user: CurrentUser, db: Session = Depends(get_db)):
    return db.query(Project).filter(Project.owner_id == current_user.id).all()


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    project = Project(owner_id=current_user.id, name=payload.name, description=payload.description)
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
