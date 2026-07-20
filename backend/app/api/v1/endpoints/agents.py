"""
AI Agents — launch and observe the role agents (CEO, Marketing, Finance,
Research, Operations). An agent runs a workspace-scoped, tool-using reasoning
loop that creates Projects/Tasks, reads/writes AI Memory, and routes important
actions through the approval queue.

Two ways to run:
  * POST /agents/{key}/stream — foreground, streams reasoning + progress as SSE.
  * POST /agents/{key}/run    — background, returns the run id immediately; poll
                                GET /agents/runs/{id} (survives a restart).
"""
import asyncio
import json

from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.agents import AGENTS, AgentRunner, get_agent, run_agent_background
from app.db.models.agent_run import AgentRun
from app.db.models.company import Company
from app.db.session import SessionLocal, get_db
from app.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentRunRequest(BaseModel):
    objective: str
    company_id: str | None = None


def _assert_company(db: Session, company_id: str | None, owner_id: str) -> None:
    if company_id is None:
        return
    exists = db.query(Company.id).filter(Company.id == company_id, Company.owner_id == owner_id).first()
    if not exists:
        raise NotFoundError(f"Company '{company_id}' not found")


def _serialize(run: AgentRun, *, full: bool) -> dict:
    agent = get_agent(run.agent_key)
    data = {
        "id": run.id,
        "agent_key": run.agent_key,
        "agent_label": agent.label if agent else run.agent_key,
        "company_id": run.company_id,
        "objective": run.objective,
        "status": run.status,
        "project_id": run.project_id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }
    if full:
        data["reasoning_log"] = json.loads(run.reasoning_log_json or "[]")
        data["result"] = run.result
    return data


@router.get("")
def list_agents(current_user: CurrentUser):
    """The roster of available agents."""
    return [
        {"key": a.key, "label": a.label, "role": a.role, "tools": a.tool_names()}
        for a in AGENTS.values()
    ]


@router.get("/runs")
def list_runs(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = None,
    agent: str | None = None,
):
    q = db.query(AgentRun).filter(AgentRun.owner_id == current_user.id)
    if company_id == "none":
        q = q.filter(AgentRun.company_id.is_(None))
    elif company_id:
        q = q.filter(AgentRun.company_id == company_id)
    if agent:
        q = q.filter(AgentRun.agent_key == agent)
    return [_serialize(r, full=False) for r in q.order_by(AgentRun.created_at.desc()).all()]


@router.get("/runs/{run_id}")
def get_run(run_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    run = db.query(AgentRun).filter(AgentRun.id == run_id, AgentRun.owner_id == current_user.id).first()
    if run is None:
        raise NotFoundError(f"Agent run '{run_id}' not found")
    return _serialize(run, full=True)


@router.post("/{agent_key}/run", status_code=202)
async def run_background(
    agent_key: str,
    payload: AgentRunRequest,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Kick off an agent in the background — returns immediately with a run id
    to poll. Execution continues independent of this request."""
    if get_agent(agent_key) is None:
        raise ValidationError(f"Unknown agent '{agent_key}'.")
    if not payload.objective.strip():
        raise ValidationError("An objective is required.")
    _assert_company(db, payload.company_id, current_user.id)

    run = AgentRunner(db).create_run(
        owner_id=current_user.id,
        company_id=payload.company_id,
        agent_key=agent_key,
        objective=payload.objective.strip(),
    )
    background_tasks.add_task(run_agent_background, run.id)
    return _serialize(run, full=False)


@router.post("/{agent_key}/stream")
async def run_stream(
    agent_key: str, payload: AgentRunRequest, current_user: CurrentUser, db: Session = Depends(get_db)
):
    """Run an agent in the foreground, streaming its reasoning and every tool
    call/result live as Server-Sent Events."""
    if get_agent(agent_key) is None:
        raise ValidationError(f"Unknown agent '{agent_key}'.")
    if not payload.objective.strip():
        raise ValidationError("An objective is required.")
    _assert_company(db, payload.company_id, current_user.id)

    run = AgentRunner(db).create_run(
        owner_id=current_user.id,
        company_id=payload.company_id,
        agent_key=agent_key,
        objective=payload.objective.strip(),
    )
    run_id = run.id

    async def event_stream():
        # Own DB session so the stream is independent of the request's session.
        stream_db = SessionLocal()
        queue: asyncio.Queue = asyncio.Queue()

        async def sink(event: dict) -> None:
            await queue.put(event)

        async def drive() -> None:
            try:
                await AgentRunner(stream_db).execute(run_id, sink=sink)
            finally:
                await queue.put(None)  # sentinel: finished

        task = asyncio.create_task(drive())
        try:
            yield f"data: {json.dumps({'type': 'run', 'run_id': run_id})}\n\n"
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            await task
            stream_db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
