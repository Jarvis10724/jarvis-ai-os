"""
HTTP surface for Google Drive-specific actions.

Both list and read execute immediately — see app.core.drive_service's
direct-action functions, each gated only by
capability_service.authorize_direct_action (capability enabled + action
permitted, no human approval needed). No write actions exist yet — see
drive_service's module docstring for how to add one.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import drive_service
from app.db.session import get_db

router = APIRouter(prefix="/drive", tags=["drive"])


@router.get("/files")
async def list_files(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = Query(None),
    query: str = Query("", description="Bare search terms or raw Drive query syntax. Empty = most recent files."),
    max_results: int = Query(10, le=50),
    all_drive: bool = Query(
        False, description="Search the whole connected Drive even if company_id is set (bypasses that company's folder scoping)."
    ),
):
    return await drive_service.list_files(
        db, owner_id=current_user.id, company_id=company_id, query=query, max_results=max_results, all_drive=all_drive
    )


@router.get("/files/{file_id}")
async def read_document(
    file_id: str, current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None)
):
    return await drive_service.read_document(db, owner_id=current_user.id, company_id=company_id, file_id=file_id)
