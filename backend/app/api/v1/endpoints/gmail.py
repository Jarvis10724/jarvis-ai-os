"""
HTTP surface for Gmail-specific actions.

Read (list/search/unread), summarize, and draft execute immediately — see
app.core.gmail_service's direct-action functions, each gated only by
capability_service.authorize_direct_action (capability enabled + action
permitted, no human approval needed). Send/forward/trash/archive/label
changes never call the Gmail API from here — they only create a pending
ApprovalRequest via gmail_service.propose_*; the real call happens later,
once approved, through app.core.capability_executors.
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import gmail_service
from app.db.session import get_db

router = APIRouter(prefix="/gmail", tags=["gmail"])


class DraftCreate(BaseModel):
    company_id: str | None = None
    to: str | None = None
    subject: str | None = None
    body: str
    thread_id: str | None = None
    #: Gmail message id to reply to — mutually exclusive with to/subject;
    #: gmail_service pulls the real thread/subject/Message-ID from it.
    reply_to_message_id: str | None = None


class SendPropose(BaseModel):
    company_id: str | None = None
    to: str
    subject: str
    body: str
    thread_id: str | None = None
    in_reply_to: str | None = None


class ForwardPropose(BaseModel):
    company_id: str | None = None
    to: str
    note: str = ""


class ScopedAction(BaseModel):
    company_id: str | None = None


class LabelsPropose(BaseModel):
    company_id: str | None = None
    add_labels: list[str] = []
    remove_labels: list[str] = []


# --- Direct actions: read, search, summarize, draft -----------------------


@router.get("/messages")
async def list_messages(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = Query(None),
    query: str = Query("", description="Gmail search syntax, e.g. 'from:x', 'has:attachment'. Empty = inbox."),
    unread_only: bool = Query(False),
    max_results: int = Query(10, le=50),
):
    return await gmail_service.list_messages(
        db,
        owner_id=current_user.id,
        company_id=company_id,
        max_results=max_results,
        query=query,
        unread_only=unread_only,
    )


@router.get("/messages/{message_id}")
async def get_message(
    message_id: str, current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None)
):
    return await gmail_service.get_message(db, owner_id=current_user.id, company_id=company_id, message_id=message_id)


@router.get("/summary")
async def summarize_unread(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = Query(None),
    max_results: int = Query(10, le=50),
):
    """Prioritized digest of unread mail — no message_id, summarizes the
    unread batch."""
    return await gmail_service.summarize(db, owner_id=current_user.id, company_id=company_id, max_results=max_results)


@router.get("/messages/{message_id}/summary")
async def summarize_message(
    message_id: str, current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None)
):
    return await gmail_service.summarize(db, owner_id=current_user.id, company_id=company_id, message_id=message_id)


@router.post("/drafts", status_code=201)
async def create_draft(payload: DraftCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    return await gmail_service.create_draft(
        db,
        owner_id=current_user.id,
        company_id=payload.company_id,
        to=payload.to,
        subject=payload.subject,
        body=payload.body,
        thread_id=payload.thread_id,
        reply_to_message_id=payload.reply_to_message_id,
    )


# --- Approval-gated actions: propose only, never executed here -----------


@router.post("/send", status_code=201)
def propose_send(payload: SendPropose, current_user: CurrentUser, db: Session = Depends(get_db)):
    return gmail_service.propose_send(
        db,
        owner_id=current_user.id,
        company_id=payload.company_id,
        to=payload.to,
        subject=payload.subject,
        body=payload.body,
        thread_id=payload.thread_id,
        in_reply_to=payload.in_reply_to,
    )


@router.post("/messages/{message_id}/forward", status_code=201)
def propose_forward(
    message_id: str, payload: ForwardPropose, current_user: CurrentUser, db: Session = Depends(get_db)
):
    return gmail_service.propose_forward(
        db, owner_id=current_user.id, company_id=payload.company_id, message_id=message_id, to=payload.to, note=payload.note
    )


@router.post("/messages/{message_id}/trash", status_code=201)
def propose_trash(message_id: str, payload: ScopedAction, current_user: CurrentUser, db: Session = Depends(get_db)):
    return gmail_service.propose_trash(db, owner_id=current_user.id, company_id=payload.company_id, message_id=message_id)


@router.post("/messages/{message_id}/archive", status_code=201)
def propose_archive(message_id: str, payload: ScopedAction, current_user: CurrentUser, db: Session = Depends(get_db)):
    return gmail_service.propose_archive(db, owner_id=current_user.id, company_id=payload.company_id, message_id=message_id)


@router.post("/messages/{message_id}/labels", status_code=201)
def propose_labels(message_id: str, payload: LabelsPropose, current_user: CurrentUser, db: Session = Depends(get_db)):
    return gmail_service.propose_modify_labels(
        db,
        owner_id=current_user.id,
        company_id=payload.company_id,
        message_id=message_id,
        add_labels=payload.add_labels,
        remove_labels=payload.remove_labels,
    )
