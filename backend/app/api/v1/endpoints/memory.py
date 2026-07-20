"""
Jarvis's long-term memory, exposed directly (not just through chat) — a
Memory page in the UI needs to browse and search this the same way the chat
tool does. See app.core.memory_service for the actual read/write/search
logic; this file is just the HTTP surface over it, with the same
ownership-scoping discipline every other endpoint in this API uses.
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import memory_service
from app.core.memory_scope import MEMORY_SCOPES
from app.db.models.memory import MEMORY_KINDS
from app.db.session import get_db

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryCreate(BaseModel):
    kind: str
    title: str
    content: str
    company_id: str | None = None
    project_id: str | None = None
    scope: str | None = None
    confidence: float | None = None
    source: str = "manual"
    source_ref: str | None = None
    extra: dict | None = None
    link_to: list[str] | None = None
    relation: str = "related_to"


class MemoryUpdate(BaseModel):
    """Edits content only — never scope/company/project. See MemoryMove for
    that, which is deliberately a separate, explicitly-audited action."""

    title: str | None = None
    content: str | None = None
    kind: str | None = None
    source_ref: str | None = None
    confidence: float | None = None
    extra: dict | None = None


class MemoryMove(BaseModel):
    scope: str
    company_id: str | None = None
    project_id: str | None = None
    note: str | None = None


class MemoryLinkCreate(BaseModel):
    to_id: str
    relation: str = "related_to"


@router.get("/kinds")
def list_kinds():
    return MEMORY_KINDS


@router.get("/scopes")
def list_scopes():
    return MEMORY_SCOPES


@router.get("")
async def search(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    q: str = Query("", description="Natural-language search query. Empty returns recent entries."),
    company_id: str | None = Query(
        "any", description="'any' = everything, 'global' = non-company memory only, or a real company id."
    ),
    project_id: str | None = Query(None, description="Narrow to memory attached to one Project."),
    kind: str | None = Query(None),
    scope: str | None = Query(None, description="Narrow to exactly one of MEMORY_SCOPES."),
    limit: int = Query(20, le=100),
):
    scoped_company_id: str | None
    if company_id == "any":
        scoped_company_id = "any"
    elif company_id in (None, "global"):
        scoped_company_id = None
    else:
        scoped_company_id = company_id

    results = await memory_service.search_memory(
        db,
        owner_id=current_user.id,
        query=q,
        company_id=scoped_company_id,
        project_id=project_id,
        kind=kind,
        scope=scope,
        limit=limit,
    )
    return results


@router.post("", status_code=201)
async def create(payload: MemoryCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    entry = await memory_service.record_memory(
        db,
        owner_id=current_user.id,
        kind=payload.kind,
        title=payload.title,
        content=payload.content,
        company_id=payload.company_id,
        project_id=payload.project_id,
        scope=payload.scope,
        confidence=payload.confidence,
        source=payload.source,
        source_ref=payload.source_ref,
        extra=payload.extra,
        link_to=payload.link_to,
        relation=payload.relation,
    )
    return memory_service.serialize_entry(entry)


@router.get("/{entry_id}")
def get_one(entry_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    return memory_service.get_entry_with_links(db, owner_id=current_user.id, entry_id=entry_id)


@router.put("/{entry_id}")
async def update(entry_id: str, payload: MemoryUpdate, current_user: CurrentUser, db: Session = Depends(get_db)):
    entry = await memory_service.update_memory(
        db,
        owner_id=current_user.id,
        entry_id=entry_id,
        title=payload.title,
        content=payload.content,
        kind=payload.kind,
        source_ref=payload.source_ref,
        confidence=payload.confidence,
        extra=payload.extra,
    )
    return memory_service.serialize_entry(entry)


@router.post("/{entry_id}/move")
async def move(entry_id: str, payload: MemoryMove, current_user: CurrentUser, db: Session = Depends(get_db)):
    entry = await memory_service.move_memory_scope(
        db,
        owner_id=current_user.id,
        entry_id=entry_id,
        scope=payload.scope,
        company_id=payload.company_id,
        project_id=payload.project_id,
        note=payload.note,
    )
    return memory_service.serialize_entry(entry)


@router.get("/{entry_id}/audit")
def get_audit(entry_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    return memory_service.get_audit_log(db, owner_id=current_user.id, entry_id=entry_id)


@router.post("/{entry_id}/links", status_code=201)
def add_link(entry_id: str, payload: MemoryLinkCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    memory_service.link_memories(
        db, owner_id=current_user.id, from_id=entry_id, to_id=payload.to_id, relation=payload.relation
    )
    return memory_service.get_entry_with_links(db, owner_id=current_user.id, entry_id=entry_id)


@router.delete("/{entry_id}", status_code=204)
def delete(entry_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    memory_service.delete_memory(db, owner_id=current_user.id, entry_id=entry_id)
