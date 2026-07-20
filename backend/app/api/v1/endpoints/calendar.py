"""
HTTP surface for Google Calendar-specific actions.

List/get events execute immediately — see app.core.calendar_service's
direct-action functions, each gated only by
capability_service.authorize_direct_action (capability enabled + action
permitted, no human approval needed). Create/update/delete never call the
Calendar API from here — they only create a pending ApprovalRequest via
calendar_service.propose_*; the real call happens later, once approved,
through app.core.capability_executors.
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import calendar_service
from app.db.session import get_db

router = APIRouter(prefix="/calendar", tags=["calendar"])


class EventCreate(BaseModel):
    company_id: str | None = None
    summary: str
    start: str
    end: str
    description: str = ""
    location: str = ""
    attendees: list[str] = []
    all_day: bool = False


class EventUpdate(BaseModel):
    company_id: str | None = None
    summary: str | None = None
    start: str | None = None
    end: str | None = None
    description: str | None = None
    location: str | None = None
    all_day: bool = False


class ScopedAction(BaseModel):
    company_id: str | None = None


# --- Direct actions: list, get ---------------------------------------------


@router.get("/events")
async def list_events(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = Query(None),
    max_results: int = Query(10, le=50),
    upcoming_only: bool = Query(True, description="Restrict to events starting now or later."),
):
    return await calendar_service.list_events(
        db, owner_id=current_user.id, company_id=company_id, max_results=max_results, upcoming_only=upcoming_only
    )


@router.get("/events/{event_id}")
async def get_event(
    event_id: str, current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None)
):
    return await calendar_service.get_event(db, owner_id=current_user.id, company_id=company_id, event_id=event_id)


# --- Approval-gated actions: propose only, never executed here -------------


@router.post("/events", status_code=201)
def propose_create_event(payload: EventCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    return calendar_service.propose_create_event(
        db,
        owner_id=current_user.id,
        company_id=payload.company_id,
        summary=payload.summary,
        start=payload.start,
        end=payload.end,
        description=payload.description,
        location=payload.location,
        attendees=payload.attendees,
        all_day=payload.all_day,
    )


@router.patch("/events/{event_id}", status_code=201)
def propose_update_event(
    event_id: str, payload: EventUpdate, current_user: CurrentUser, db: Session = Depends(get_db)
):
    return calendar_service.propose_update_event(
        db,
        owner_id=current_user.id,
        company_id=payload.company_id,
        event_id=event_id,
        summary=payload.summary,
        start=payload.start,
        end=payload.end,
        description=payload.description,
        location=payload.location,
        all_day=payload.all_day,
    )


@router.delete("/events/{event_id}", status_code=201)
def propose_delete_event(event_id: str, payload: ScopedAction, current_user: CurrentUser, db: Session = Depends(get_db)):
    return calendar_service.propose_delete_event(
        db, owner_id=current_user.id, company_id=payload.company_id, event_id=event_id
    )
