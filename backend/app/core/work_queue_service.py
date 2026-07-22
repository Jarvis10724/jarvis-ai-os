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
from app.core import brand_brain_service, capability_service
from app.core.capability_executors import register_executor
from app.db.models.agent_run import AgentRun
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
    "real_world=false. For every subtask also give a one-sentence `why` explaining what it "
    "contributes to the goal — for a real-world step this is what the human reads before approving.\n"
    'Respond with ONLY JSON: {"subtasks":[{"title":"...","real_world":false,"why":"..."}]}.'
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


def _new_subtask(title: str, real_world: bool, why: str = "") -> dict:
    return {
        "id": str(uuid4()),
        "title": title[:300],
        # Why this step exists — carried into the approval brief so a
        # real-world step can be judged on its purpose, not just its wording.
        "why": (why or "")[:400],
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
    subtasks = [
        _new_subtask(s.get("title", "Subtask"), s.get("real_world", False), s.get("why", "")) for s in raw[:8]
    ]
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

    for index, st in enumerate(subtasks):
        if st["status"] not in (PLANNED,):
            continue
        st["status"] = WORKING
        _save()
        yield {"type": "subtask", "id": st["id"], "title": st["title"], "status": WORKING}

        if st["real_world"]:
            # Every real-world step goes through the Approval Center, carrying a
            # brief a human can decide on and a group_id tying it to this plan,
            # so the whole plan can be approved at once and run in order.
            approval = capability_service.propose_action(
                db,
                owner_id=owner_id,
                capability_name=WORK_QUEUE_KEY,
                action_type="execute_step",
                payload={"title": st["title"], "run_id": run.id, "subtask_id": st["id"]},
                company_id=run.company_id,
                requested_by=owner_id,
                brief={"reason": st.get("why") or f"Part of: {run.objective}"},
                group_id=run.id,
                group_label=run.objective[:200],
                sequence=index,
            )
            st["status"] = WAITING
            st["approval_id"] = approval["id"]
            _save()
            yield {"type": "subtask", "id": st["id"], "status": WAITING, "approval_id": approval["id"]}
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


# ---------------------------------------------------------------------------
# Approval Center integration: what happens after a human decides
# ---------------------------------------------------------------------------


def _load(db: Session, run: AgentRun) -> list[dict]:
    return json.loads(run.subtasks_json) if run.subtasks_json else []


def _store(db: Session, run: AgentRun, subtasks: list[dict]) -> None:
    run.subtasks_json = json.dumps(subtasks)
    waiting = any(s["status"] == WAITING for s in subtasks)
    planned = any(s["status"] == PLANNED for s in subtasks)
    run.status = "waiting" if waiting else ("running" if planned else "completed")
    run.result = (
        "Some steps are waiting for your approval."
        if waiting
        else ("Work in progress." if planned else "All steps complete.")
    )
    db.commit()


async def _run_remaining_steps(db: Session, *, owner_id: str, run: AgentRun) -> list[dict]:
    """Continue the plan after an approval unblocks it: internal steps run
    autonomously, and the next real-world step raises its own approval and
    stops there. This is what makes approving a plan execute it in sequence
    rather than one step at a time."""
    events: list[dict] = []
    async for event in execute_stream(db, owner_id=owner_id, run_id=run.id):
        events.append(event)
    return events


async def complete_approved_step(
    db: Session, *, owner_id: str, company_id: str | None, action_type: str, payload: dict
) -> dict:
    """Executor for an approved `work_queue · execute_step`.

    The step's real-world effect belongs to whichever integration owns it —
    this does NOT reach out to Gmail, Shopify, or anything else on its own.
    What it does is record that consent was given, produce the work product
    Jarvis can produce, and let the rest of the plan proceed. Registered with
    capability_executors, so the Approval Center runs it automatically the
    moment the step is approved."""
    run_id, subtask_id = payload.get("run_id"), payload.get("subtask_id")
    if not run_id:
        return {"completed": False, "detail": "No run attached to this step."}
    run = get_run(db, owner_id=owner_id, run_id=run_id)
    subtasks = _load(db, run)
    step = next((s for s in subtasks if s["id"] == subtask_id), None)
    if step is None:
        return {"completed": False, "detail": "Step is no longer part of this plan."}

    provider = get_ai_provider()
    try:
        res = await provider.complete(
            messages=[
                Message(
                    role="system",
                    content="You are Jarvis carrying out one approved step of a plan. The human has "
                    "approved it. Produce the concrete work product for this step — the actual "
                    "content, decision, or instruction. Be specific and brief.",
                ),
                Message(role="user", content=f"Overall goal: {run.objective}\n\nApproved step: {step['title']}"),
            ],
            max_tokens=900,
        )
        step["result"] = (res.text or "").strip()[:4000]
    except Exception as exc:  # noqa: BLE001
        step["result"] = f"(approved, but the work product could not be generated: {exc})"
    step["status"] = COMPLETE
    _store(db, run, subtasks)

    # Unblock the rest of the plan: run whatever is still PLANNED behind it.
    await _run_remaining_steps(db, owner_id=owner_id, run=run)
    db.refresh(run)
    return {"completed": True, "run_id": run.id, "run_status": run.status}


async def replan_after_rejection(
    db: Session, *, owner_id: str, run_id: str, subtask_id: str | None, rejection_note: str | None
) -> dict:
    """A rejected step is a constraint, not a dead end. Ask the planner to
    revise the REMAINING work so the goal can still be pursued without the
    rejected step — then queue the revision as ordinary planned subtasks.

    Returns what changed, so the UI can say so plainly. If the planner can't
    find a way around it, the plan simply stops with the rejection recorded,
    which is a legitimate outcome rather than a failure to paper over."""
    run = get_run(db, owner_id=owner_id, run_id=run_id)
    subtasks = _load(db, run)
    rejected = next((s for s in subtasks if s["id"] == subtask_id), None)
    if rejected is not None:
        rejected["status"] = COMPLETE
        rejected["result"] = f"Rejected by you. {rejection_note or ''}".strip()

    remaining = [s for s in subtasks if s["status"] in (PLANNED, WAITING)]
    done = [s for s in subtasks if s["status"] == COMPLETE]
    provider = get_ai_provider()
    try:
        res = await provider.complete(
            messages=[
                Message(
                    role="system",
                    content=(
                        "You are Jarvis re-planning. The human REJECTED one step of your plan. Revise the "
                        "remaining work so the goal can still be pursued WITHOUT the rejected step and "
                        "without repeating what's already done. If the rejection makes the goal "
                        'unreachable, return an empty list.\n'
                        'Respond with ONLY JSON: {"subtasks":[{"title":"...","real_world":false,"why":"..."}]}'
                    ),
                ),
                Message(
                    role="user",
                    content=(
                        f"Goal: {run.objective}\n"
                        f"Rejected step: {rejected['title'] if rejected else '(unknown)'}\n"
                        f"Reason given: {rejection_note or '(none given)'}\n"
                        f"Already done: {[s['title'] for s in done]}\n"
                        f"Still queued: {[s['title'] for s in remaining]}"
                    ),
                ),
            ],
            max_tokens=800,
            temperature=0.3,
        )
        revised = _extract_json(res.text).get("subtasks", [])
    except Exception:
        revised = []

    # The rejection invalidates what was queued behind it — replace, don't stack.
    kept = [s for s in subtasks if s["status"] == COMPLETE]
    new_steps = [
        _new_subtask(s.get("title", "Subtask"), s.get("real_world", False), s.get("why", "")) for s in revised[:6]
    ]
    _store(db, run, kept + new_steps)

    if not new_steps:
        run.result = "Stopped: the rejected step was required, and no alternative path was found."
        db.commit()

    return {
        "run_id": run.id,
        "replanned": bool(new_steps),
        "new_steps": [s["title"] for s in new_steps],
        "run_status": run.status,
    }


register_executor(WORK_QUEUE_KEY, complete_approved_step)
