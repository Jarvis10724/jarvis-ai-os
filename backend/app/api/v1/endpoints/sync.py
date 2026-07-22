"""
The one stream every Jarvis client holds open.

`GET /sync/stream` stays connected for the life of the tab and emits a frame
whenever anything in this account changes. Clients re-fetch through their normal
endpoints — the stream is a signal, never data.

A heartbeat goes out every 20 seconds. It keeps intermediaries from closing an
idle connection, and it carries the current version stamps, so a client that
missed events while its device was asleep notices it is behind on the very next
beat instead of waiting for the next change.
"""
import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser
from app.core import sync_service

router = APIRouter(prefix="/sync", tags=["sync"])

HEARTBEAT_SECONDS = 20


@router.get("/versions")
def versions(current_user: CurrentUser, company_id: str | None = Query(None)):
    """Current version stamps. A client compares these against what it last saw
    to decide whether it fell behind — after sleep, after backgrounding, or
    after a reconnect."""
    return sync_service.versions_for(current_user.id, company_id)


@router.get("/stream")
async def stream(current_user: CurrentUser):
    """Long-lived change feed for this account, scoped by owner so one account's
    events can never reach another's client."""
    owner_id = current_user.id
    queue = sync_service.subscribe(owner_id)

    async def frames():
        try:
            # Tell the client where it stands immediately, so a reconnecting
            # device can reconcile before the first change arrives.
            hello = {"type": "hello", **sync_service.versions_for(owner_id)}
            yield f"data: {json.dumps(hello)}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    event = {"type": "heartbeat", **sync_service.versions_for(owner_id)}
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            sync_service.unsubscribe(owner_id, queue)

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Without this, a proxy that buffers would hold frames back and the
            # feed would arrive in useless bursts.
            "X-Accel-Buffering": "no",
        },
    )
