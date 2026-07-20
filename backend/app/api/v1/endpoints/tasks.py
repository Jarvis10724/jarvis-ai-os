from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.models.company import Company
from app.db.models.task import Task
from app.db.session import get_db
from app.exceptions import NotFoundError

router = APIRouter(tags=["tasks"])


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    status: str = "backlog"
    division: str | None = None
    assignee: str | None = None
    due_date: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    division: str | None = None
    assignee: str | None = None
    due_date: str | None = None


class TaskRead(BaseModel):
    id: str
    company_id: str | None
    title: str
    description: str | None
    status: str
    division: str | None
    assignee: str | None
    due_date: str | None

    model_config = {"from_attributes": True}


def _get_owned_company(company_id: str, current_user, db: Session) -> Company:
    company = db.query(Company).filter(Company.id == company_id, Company.owner_id == current_user.id).first()
    if not company:
        raise NotFoundError(f"Company '{company_id}' not found")
    return company


def _get_owned_task(task_id: str, current_user, db: Session) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise NotFoundError(f"Task '{task_id}' not found")
    return task


# Standalone, company-scoped tasks — the Project Manager kanban board. Not
# nested under a Project; project_id stays null for these. See
# app/api/v1/endpoints/projects.py for the older project-nested task flow
# (still used by plugin-run tasks, untouched here).


@router.get("/companies/{company_id}/tasks", response_model=list[TaskRead])
def list_company_tasks(company_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    _get_owned_company(company_id, current_user, db)
    return db.query(Task).filter(Task.company_id == company_id).order_by(Task.created_at.desc()).all()


@router.post("/companies/{company_id}/tasks", response_model=TaskRead, status_code=201)
def create_company_task(
    company_id: str, payload: TaskCreate, current_user: CurrentUser, db: Session = Depends(get_db)
):
    _get_owned_company(company_id, current_user, db)
    task = Task(
        company_id=company_id,
        owner_id=current_user.id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        division=payload.division,
        assignee=payload.assignee,
        due_date=payload.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: str, payload: TaskUpdate, current_user: CurrentUser, db: Session = Depends(get_db)):
    task = _get_owned_task(task_id, current_user, db)
    for field in ("title", "description", "status", "division", "assignee", "due_date"):
        value = getattr(payload, field)
        if value is not None:
            setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    task = _get_owned_task(task_id, current_user, db)
    db.delete(task)
    db.commit()
