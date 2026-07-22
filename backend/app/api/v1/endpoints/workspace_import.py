"""
Workspace import HTTP surface.

POST /workspace-import/scan — walk every connected source for one workspace and
stream progress as it goes (SSE, same frame shape as the Work Queue stream).

Read-only against the outside world: it imports FROM Shopify, Gmail and Drive
and never writes back to them.
"""
import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import drive_service, workspace_import_service
from app.db.session import SessionLocal, get_db

router = APIRouter(prefix="/workspace-import", tags=["workspace-import"])

#: Fetched Drive assets are cached on disk so opening the Brand page doesn't
#: re-download the logo on every render (and doesn't spend a Drive API call).
ASSET_CACHE = Path("data/asset_cache")


@router.get("/asset")
async def asset(
    current_user: CurrentUser,
    company_id: str = Query(...),
    file_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """One Drive file's bytes, fetched with the WORKSPACE's own credentials so
    an image stored in Drive can actually be shown in the app. Cached on disk
    after the first fetch; scoped per company, so no workspace can read
    another's files."""
    ASSET_CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{company_id}:{file_id}".encode()).hexdigest()
    cached = ASSET_CACHE / key
    meta_path = ASSET_CACHE / f"{key}.type"
    if cached.exists() and meta_path.exists():
        return Response(
            content=cached.read_bytes(),
            media_type=meta_path.read_text() or "application/octet-stream",
            headers={"Cache-Control": "private, max-age=86400"},
        )

    data = await drive_service.download_asset(
        db, owner_id=current_user.id, company_id=company_id, file_id=file_id
    )
    content = data.get("content") or b""
    media_type = data.get("mime_type") or "application/octet-stream"
    try:
        cached.write_bytes(content)
        meta_path.write_text(media_type)
    except OSError:  # a cache miss is survivable; failing the request isn't
        pass
    return Response(
        content=content, media_type=media_type,
        headers={"Cache-Control": "private, max-age=86400"},
    )


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


@router.post("/extract")
async def extract(
    current_user: CurrentUser,
    company_id: str = Query(...),
    section: str = Query("brand"),
    db: Session = Depends(get_db),
):
    """Open the workspace's own files and pull STRUCTURED knowledge out of
    them, rather than another list of links. Stored on the section, alongside
    (never over) anything the operator wrote. Fields the sources don't state
    come back null — an empty field is a fact, an invented one is a liability."""
    if section != "brand":
        return {"section": section, "supported": False,
                "message": f"Deep extraction for '{section}' isn't implemented yet."}
    data = await workspace_import_service.extract_brand(
        db, owner_id=current_user.id, company_id=company_id
    )
    return {"section": "brand", "supported": True, "data": data}


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
