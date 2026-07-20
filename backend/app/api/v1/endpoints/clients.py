"""
Clients — the agency-style entity used by the Website Builder's "Build Client
Website" mode. A user owns clients, optionally scoped to a company workspace so
switching companies re-scopes the list. Projects and workspace sessions built
for a client carry its `client_id`, keeping client work separate from the
company's own.
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.models.client import Client
from app.db.models.company import Company
from app.db.models.project import Project
from app.db.session import get_db
from app.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/clients", tags=["clients"])


class ClientCreate(BaseModel):
    name: str
    company_id: str | None = None
    website: str | None = None
    notes: str | None = None


class ClientUpdate(BaseModel):
    name: str | None = None
    website: str | None = None
    notes: str | None = None


def _assert_company(db: Session, company_id: str | None, owner_id: str) -> None:
    if company_id is None:
        return
    exists = db.query(Company.id).filter(Company.id == company_id, Company.owner_id == owner_id).first()
    if not exists:
        raise NotFoundError(f"Company '{company_id}' not found")


def _owned(db: Session, client_id: str, owner_id: str) -> Client:
    c = db.query(Client).filter(Client.id == client_id, Client.owner_id == owner_id).first()
    if not c:
        raise NotFoundError(f"Client '{client_id}' not found")
    return c


def _serialize(db: Session, c: Client) -> dict:
    project_count = db.query(Project.id).filter(Project.client_id == c.id).count()
    return {
        "id": c.id,
        "name": c.name,
        "company_id": c.company_id,
        "website": c.website,
        "notes": c.notes,
        "project_count": project_count,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("")
def list_clients(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = None):
    q = db.query(Client).filter(Client.owner_id == current_user.id)
    if company_id == "none":
        q = q.filter(Client.company_id.is_(None))
    elif company_id:
        q = q.filter(Client.company_id == company_id)
    clients = q.order_by(Client.created_at.desc()).all()
    return [_serialize(db, c) for c in clients]


@router.post("", status_code=201)
def create_client(payload: ClientCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    name = (payload.name or "").strip()
    if not name:
        raise ValidationError("Client name is required.")
    _assert_company(db, payload.company_id, current_user.id)
    client = Client(
        owner_id=current_user.id,
        company_id=payload.company_id,
        name=name[:255],
        website=(payload.website or None),
        notes=(payload.notes or None),
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return _serialize(db, client)


@router.get("/{client_id}")
def get_client(client_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    c = _owned(db, client_id, current_user.id)
    data = _serialize(db, c)
    projects = (
        db.query(Project).filter(Project.client_id == c.id).order_by(Project.created_at.desc()).all()
    )
    data["projects"] = [{"id": p.id, "name": p.name, "status": p.status} for p in projects]
    return data


@router.patch("/{client_id}")
def update_client(client_id: str, payload: ClientUpdate, current_user: CurrentUser, db: Session = Depends(get_db)):
    c = _owned(db, client_id, current_user.id)
    if payload.name is not None and payload.name.strip():
        c.name = payload.name.strip()[:255]
    if payload.website is not None:
        c.website = payload.website or None
    if payload.notes is not None:
        c.notes = payload.notes or None
    db.commit()
    db.refresh(c)
    return _serialize(db, c)
