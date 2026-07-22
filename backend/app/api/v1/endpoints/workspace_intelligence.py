"""
Workspace Intelligence HTTP surface (Phase 3 #4).

GET /workspace-intelligence  — the AI reading of a workspace + the signals it
                               was based on (cached briefly; ?refresh=true
                               forces a fresh read).
GET /workspace-intelligence/signals — just the raw signals, no AI call.

Recommendations are acted on through the existing Work Queue (POST /work-queue),
so anything with real-world consequences still stops at the approval gate.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import workspace_intelligence_service
from app.db.session import get_db

router = APIRouter(prefix="/workspace-intelligence", tags=["workspace-intelligence"])


@router.get("")
async def analyze(
    current_user: CurrentUser,
    company_id: str = Query(...),
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
):
    return await workspace_intelligence_service.analyze(
        db, owner_id=current_user.id, company_id=company_id, refresh=refresh
    )


@router.get("/signals")
def signals(current_user: CurrentUser, company_id: str = Query(...), db: Session = Depends(get_db)):
    return workspace_intelligence_service.gather(db, owner_id=current_user.id, company_id=company_id)
