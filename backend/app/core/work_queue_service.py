"""
Autonomous Work Queue — Jarvis breaks a large request into an ordered list of
subtasks and works through them, tracking each through
Planned → Working → Waiting for Approval → Complete and streaming progress.

Autonomy is APPROVAL-GATED (the chosen policy): internal/read subtasks (research,
drafting, planning, summarizing, generating content) run autonomously; any
subtask with real-world consequences (send email, purchase, publish, change
inventory, financial action) creates an approval and stops at
"waiting_approval" until a human approves — nothing with consequences happens on
its own.

Built on the existing AgentRun (its new subtasks_json column) so it shares
workspace scoping, persistence, and the Approvals system — no parallel
subsystem, and every existing integration/API is untouched.
"""
import json
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.core import brand_brain_service
from app.db.models.agent_run import AgentRun
from app.db.models.capability import ApprovalRequest
from app.db.models.company import Company
from app.exceptions import NotFoundError

WORK_QUEUE_KEY = "work_queue"

PLANNED = "planned"
WORKING = "working"
WAITING = "waiting_approval"
COMPLETE = "complete"

_PLAN_SYSTEM = (
    "You are Jarvis's planner. Break the user's request into a short ordered list of concrete "
    "subtasks (2 to 6). For each subtask decide whether carrying it out has REAL-WORLD "
    "CONSEQUENCES needing human approval: sending an email, making a purchase, publishing, "
    "changing inventory, or any financial action are real_world=true. Research, drafting, "
    "planning, summarizing, creating an internal task/project, or generating content are "
    'real_world=false. Respond with ONLY JSON: {"subtasks":[{"title":"...","real_world":false}]}.'
)


def _owned_company(db: Session, company_id: str | None, owner_id: str) -> None:
    if company_id and not db.query(Company).filter(Company.id == company_id, Company.owner_id == owner_id).first():
        raise NotFoundError(f"Company '{company_id}' not found")


def _extract_json(text: str) -> dict:
    s = text.strip()
    if "```" in s:
        parts = s.split("```")
        s = parts[1] if len(parts) > 1 else s
        if s.lstrip().startswith("json"):
            s = s.lstrip()[4:]
    a, b = s.find("{"), s.rfind("}")
    if a >= 0 and b > a:
        s = s[a : b + 1]
    return json.loads(s)


def _new_subtask(title: str, real_world: bool) -> dict:
    return {
        "id": str(uuid4()),
        "title": title[:300],
        "real_world": bool(real_world),
        "status": PLANNED,
        "result": None,
        "approval_id": None,
    }


def get_run(db: Session, *, owner_id: str, run_id: str) -> AgentRun:
    run = (
        db.query(AgentRun)
        .filter(AgentRun.id == run_id, AgentRun.owner_id == owner_id, AgentRun.agent_key == WORK_QUEUE_KEY)
        .first()
    )
    if not run:
        raise NotFoundError(f"Work run '{run_id}' not found")
    return run


def serialize(run: AgentRun) -> dict:
    return {
        "id": run.id,
        "company_id": run.company_id,
        "objective": run.objective,
        "status": run.status,
        "result": run.result,
        "subtasks": json.loads(run.subtasks_json) if run.subtasks_json else [],
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


async def plan(db: Session, *, owner_id: str, company_id: str | None, request: str) -> AgentRun:
    """Decompose a request into ordered subtasks (Planned) and persist a work
    run. Grounds the planner in the workspace's Brand Brain when available."""
    _owned_company(db, company_id, owner_id)
    ctx = brand_brain_service.brand_prompt_context(db, company_id) if company_id else ""
    provider = get_ai_provider()
    try:
        result = await provider.complete(
            messages=[
                Message(role="system", content=_PLAN_SYSTEM + ctx),
                Message(role="user", content=request),
            ],
            max_tokens=800,
            temperature=0.3,
        )
        raw = _extract_json(result.text).get("subtasks", [])
    except Exception:
        raw = []
    subtasks = [_new_subtask(s.get("title", "Subtask"), s.get("real_world", False)) for s in raw[:8]]
    if not subtasks:
        subtasks = [_new_subtask(request, False)]

    run = AgentRun(
        owner_id=owner_id,
        company_id=company_id,
        agent_key=WORK_QUEUE_KEY,
        objective=request,
        status="planned",
        subtasks_json=json.dumps(subtasks),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


async def execute_stream(db: Session, *, owner_id: str, run_id: str):
    """Work through the run's planned subtasks, yielding an event per state
    change (for SSE). Internal subtasks are executed autonomously (Jarvis
    produces the work); real-world subtasks create an approval and stop at
    waiting_approval. Idempotent-ish: only PLANNED subtasks are (re)processed."""
    run = get_run(db, owner_id=owner_id, run_id=run_id)
    subtasks = json.loads(run.subtasks_json) if run.subtasks_json else []
    run.status = "running"
    db.commit()
    yield {"type": "run", "run_id": run.id, "status": "running"}

    provider = get_ai_provider()

    def _save():
        run.subtasks_json = json.dumps(subtasks)
        db.commit()

    for st in subtasks:
        if st["status"] not in (PLANNED,):
            continue
        st["status"] = WORKING
        _save()
        yield {"type": "subtask", "id": st["id"], "title": st["title"], "status": WORKING}

        if st["real_world"]:
            approval = ApprovalRequest(
                owner_id=owner_id,
                company_id=run.company_id,
                capability_name=WORK_QUEUE_KEY,
                action_type="execute_step",
                payload_json=json.dumps({"title": st["title"], "run_id": run.id, "subtask_id": st["id"]}),
                status="pending",
                requested_by=owner_id,
            )
            db.add(approval)
            db.commit()
            db.refresh(approval)
            st["status"] = WAITING
            st["approval_id"] = approval.id
            _save()
            yield {"type": "subtask", "id": st["id"], "status": WAITING, "approval_id": approval.id}
        else:
            try:
                res = await provider.complete(
                    messages=[
                        Message(
                            role="system",
                            content="You are Jarvis executing one subtask of a larger plan. "
                            "Produce the concrete work product for this subtask concisely.",
                        ),
                        Message(role="user", content=f"Overall goal: {run.objective}\n\nSubtask: {st['title']}"),
                    ],
                    max_tokens=700,
                )
                st["result"] = (res.text or "").strip()[:4000]
            except Exception as exc:  # noqa: BLE001
                st["result"] = f"(could not complete: {exc})"
            st["status"] = COMPLETE
            _save()
            yield {"type": "subtask", "id": st["id"], "status": COMPLETE, "result": st["result"]}

    waiting = any(s["status"] == WAITING for s in subtasks)
    run.status = "waiting" if waiting else "completed"
    run.result = (
        "Some steps are waiting for your approval." if waiting else "All steps complete."
    )
    _save()
    yield {"type": "done", "status": run.status}
