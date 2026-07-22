"""
AI Command Center HTTP surface (Phase 3 #3).

POST /command-center/route — classify a request to the subsystem that should
handle it, so "Ask Jarvis" never makes the user choose a tool.

Routing only decides; execution stays in the existing subsystems (studio Quick
Actions, chat + its tools/approval gate, Work Queue, or a navigation), so every
integration, approval, and workspace-isolation rule is preserved.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import command_center_service
from app.db.session import get_db

router = APIRouter(prefix="/command-center", tags=["command-center"])


class RouteRequest(BaseModel):
    request: str
    company_id: str | None = None
    #: recent conversation turns ({role, content}) so routing keeps context.
    history: list[dict] | None = None


@router.get("/destinations")
def destinations(current_user: CurrentUser):
    """The routable destination catalog (data-driven — adding one here is all
    it takes for the Command Center to route to it)."""
    return [
        {"key": k, "label": v["label"], "mode": v["mode"], "target": v["target"], "when": v["when"]}
        for k, v in command_center_service.DESTINATIONS.items()
    ]


@router.post("/route")
async def route(payload: RouteRequest, current_user: CurrentUser, db: Session = Depends(get_db)):
    return await command_center_service.route(
        db,
        owner_id=current_user.id,
        company_id=payload.company_id,
        request=payload.request,
        history=payload.history,
    )
