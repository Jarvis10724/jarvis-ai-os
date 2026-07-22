"""
Workspace import HTTP surface.

POST /workspace-import/scan — walk every connected source for one workspace and
stream progress as it goes (SSE, same frame shape as the Work Queue stream).

Read-only against the outside world: it imports FROM Shopify, Gmail and Drive
and never writes back to them.
"""
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import workspace_import_service
from app.db.session import SessionLocal, get_db

router = APIRouter(prefix="/workspace-import", tags=["workspace-import"])


@router.post("/scan")
async def scan(current_user: CurrentUser, company_id: str = Query(...)):
    """Streams `data: {json}` progress frames while scanning, then a final
    `done` frame carrying the totals, the per-section breakdown, and an honest
    list of what could NOT be reached."""
    owner_id = current_user.id

    async def frames():
        # Its own session: the request-scoped one closes when the response
        # starts streaming.
        db: Session = SessionLocal()
        try:
            async for event in workspace_import_service.scan(
                db, owner_id=owner_id, company_id=company_id
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:  # noqa: BLE001 - surface it in-stream
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:300]})}\n\n"
        finally:
            db.close()

    return StreamingResponse(frames(), media_type="text/event-stream")


@router.get("/summary")
def summary(current_user: CurrentUser, company_id: str = Query(...), db: Session = Depends(get_db)):
    """What the knowledge base currently holds for this workspace, by source
    and by section — so the operator can see coverage without re-scanning."""
    from sqlalchemy import func

    from app.db.models.memory import MemoryEntry

    rows = (
        db.query(MemoryEntry.source, func.count(MemoryEntry.id))
        .filter(
            MemoryEntry.owner_id == current_user.id,
            MemoryEntry.company_id == company_id,
            MemoryEntry.source.like("import:%"),
        )
        .group_by(MemoryEntry.source)
        .all()
    )
    by_section: dict[str, int] = {}
    entries = (
        db.query(MemoryEntry)
        .filter(
            MemoryEntry.owner_id == current_user.id,
            MemoryEntry.company_id == company_id,
            MemoryEntry.source.like("import:%"),
        )
        .all()
    )
    for entry in entries:
        try:
            section = (json.loads(entry.extra_json) if entry.extra_json else {}).get("section")
        except (TypeError, ValueError):
            section = None
        if section:
            by_section[section] = by_section.get(section, 0) + 1
    return {
        "total": len(entries),
        "by_source": {source: count for source, count in rows},
        "by_section": by_section,
    }
