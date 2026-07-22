"""
Autonomous Work Queue HTTP surface (Phase 3).

POST /work-queue           — decompose a request into subtasks (Planned).
POST /work-queue/{id}/stream — work through them, streaming state changes (SSE).
GET  /work-queue/{id}      — current state (poll / restore).
GET  /work-queue           — recent work runs for the workspace.

Approval-gated: real-world subtasks create an approval and stop at
waiting_approval; nothing with real-world consequences runs without a human.
Built on AgentRun, so it reuses workspace scoping + the Approvals system.
"""
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import work_queue_service
from app.db.models.agent_run import AgentRun
from app.db.session import SessionLocal, get_db

router = APIRouter(prefix="/work-queue", tags=["work-queue"])


class PlanRequest(BaseModel):
    request: str
    company_id: str | None = None


@router.post("")
async def create_plan(payload: PlanRequest, current_user: CurrentUser, db: Session = Depends(get_db)):
    run = await work_queue_service.plan(
        db, owner_id=current_user.id, company_id=payload.company_id, request=payload.request
    )
    return work_queue_service.serialize(run)


@router.get("")
def list_runs(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None), limit: int = Query(20, le=50)):
    q = db.query(AgentRun).filter(
        AgentRun.owner_id == current_user.id, AgentRun.agent_key == work_queue_service.WORK_QUEUE_KEY
    )
    if company_id:
        q = q.filter(AgentRun.company_id == company_id)
    runs = q.order_by(AgentRun.created_at.desc()).limit(limit).all()
    return [work_queue_service.serialize(r) for r in runs]


@router.get("/{run_id}")
def get_run(run_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    return work_queue_service.serialize(work_queue_service.get_run(db, owner_id=current_user.id, run_id=run_id))


@router.post("/{run_id}/stream")
async def stream(run_id: str, current_user: CurrentUser):
    owner_id = current_user.id

    async def event_stream():
        # Own DB session so the stream is independent of the request's session.
        stream_db = SessionLocal()
        try:
            async for event in work_queue_service.execute_stream(stream_db, owner_id=owner_id, run_id=run_id):
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
