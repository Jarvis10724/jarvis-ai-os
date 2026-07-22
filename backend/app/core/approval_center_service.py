"""
The Approval Center — one queue for every real-world action Jarvis wants to
take, and the machinery that carries out what you approve.

capability_service owns a single approval's lifecycle (propose → approve /
reject / edit → execute) and its audit trail. This module is the layer above:

  * the QUEUE — every pending request for a workspace, standalone ones and
    execution plans alike, ordered so it reads the way the work will happen.
    It lives in the database, so it survives a refresh, a restart, and a
    different device.
  * PLAN decisions — approve or reject an entire plan, or any single step.
  * SEQUENTIAL EXECUTION — approving runs the steps in order, stopping at the
    first failure rather than plowing on.
  * RE-PLANNING — a rejected step doesn't just die; the plan it belonged to is
    asked to re-plan around the rejection.

Execution itself is delegated to app.core.capability_executors, which is where
a capability registers what "actually do it" means. A capability with no
executor registered stays 'approved' — consent recorded, nothing performed —
which is the honest resting state, never a fabricated 'executed'.
"""
import asyncio
import json

from sqlalchemy.orm import Session

from app.core import capability_executors, capability_service
from app.db.models.capability import ApprovalRequest, CapabilityAuditLog
from app.exceptions import NotFoundError, ValidationError
from app.logging_config import get_logger

logger = get_logger(__name__)

#: Terminal-ish states a plan step can be left in after a run.
DONE_STATES = ("executed", "rejected")


def _owned(db: Session, request_id: str, owner_id: str) -> ApprovalRequest:
    req = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.id == request_id, ApprovalRequest.owner_id == owner_id)
        .first()
    )
    if not req:
        raise NotFoundError(f"Approval request '{request_id}' not found (or it isn't yours).")
    return req


def _plan_rows(db: Session, *, owner_id: str, group_id: str) -> list[ApprovalRequest]:
    rows = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.owner_id == owner_id, ApprovalRequest.group_id == group_id)
        .order_by(ApprovalRequest.sequence.asc(), ApprovalRequest.created_at.asc())
        .all()
    )
    if not rows:
        raise NotFoundError(f"Approval plan '{group_id}' not found (or it isn't yours).")
    return rows


def queue(db: Session, *, owner_id: str, company_id: str | None = None, status: str = "pending") -> dict:
    """The workspace's approval queue: plans (grouped, in execution order) and
    standalone requests. Persisted, so this is identical after a refresh or a
    restart — the queue is the database, not a client-side list."""
    q = db.query(ApprovalRequest).filter(ApprovalRequest.owner_id == owner_id)
    if company_id:
        q = q.filter(ApprovalRequest.company_id == company_id)
    if status and status != "all":
        q = q.filter(ApprovalRequest.status == status)
    rows = q.order_by(ApprovalRequest.created_at.desc()).all()

    plans: dict[str, dict] = {}
    standalone: list[dict] = []
    for row in rows:
        item = capability_service.serialize_approval(row)
        if row.group_id:
            plan = plans.setdefault(
                row.group_id,
                {
                    "group_id": row.group_id,
                    "label": row.group_label or "Execution plan",
                    "company_id": row.company_id,
                    "steps": [],
                },
            )
            plan["steps"].append(item)
        else:
            standalone.append(item)

    for plan in plans.values():
        plan["steps"].sort(key=lambda s: s["sequence"])
        plan["pending_steps"] = sum(1 for s in plan["steps"] if s["status"] == "pending")

    return {
        "plans": sorted(plans.values(), key=lambda p: p["steps"][0]["created_at"] or "", reverse=True),
        "standalone": standalone,
        "pending_count": sum(1 for r in rows if r.status == "pending"),
    }


async def decide(
    db: Session,
    *,
    owner_id: str,
    request_id: str,
    approve: bool,
    payload: dict | None = None,
    note: str | None = None,
    device: str | None = None,
) -> dict:
    """Decide ONE request. `payload` edits it first — "edit then approve" is a
    single reviewed decision, not an edit that quietly loses its approval.

    On approve, the registered executor runs immediately; if the capability has
    none, the request stays 'approved' (consent recorded, nothing performed).
    On reject, the plan this step belongs to is asked to re-plan around it.

    `device` records where the decision came from (iPhone or desktop) — the
    same request is visible on both, so the audit needs to say which one
    actually decided it."""
    async with _decision_lock(request_id):
        return await _decide_once(
            db, owner_id=owner_id, request_id=request_id, approve=approve,
            payload=payload, note=note, device=device,
        )


#: One approval, one execution. Two taps on a phone — or the same request
#: approved on the phone and the desktop at once — arrive as concurrent
#: requests that can BOTH read status='pending' before either writes, and the
#: second one would send a second mutation to Shopify. These locks serialize
#: decisions per request so the second caller finds the real status and is
#: told it's already decided.
#:
#: This is a single-process guard, which is what this deployment is (one
#: uvicorn worker, one SQLite file). The status check inside is the durable
#: half: it survives restarts and would still catch a duplicate across
#: processes, it just wouldn't order them.
_DECISION_LOCKS: dict[str, asyncio.Lock] = {}


def _decision_lock(request_id: str) -> asyncio.Lock:
    return _DECISION_LOCKS.setdefault(request_id, asyncio.Lock())


async def _decide_once(
    db: Session,
    *,
    owner_id: str,
    request_id: str,
    approve: bool,
    payload: dict | None = None,
    note: str | None = None,
    device: str | None = None,
) -> dict:
    req = _owned(db, request_id, owner_id)
    if req.status != "pending":
        raise ValidationError(f"Approval request is '{req.status}', not pending.")

    if device:
        db.add(
            CapabilityAuditLog(
                owner_id=owner_id, company_id=req.company_id, capability_name=req.capability_name,
                approval_request_id=request_id, action="decided",
                note=f"{'approved' if approve else 'rejected'} from {device}"[:500],
            )
        )
        db.commit()

    if payload is not None:
        capability_service.edit_action(db, owner_id=owner_id, request_id=request_id, payload=payload)

    if not approve:
        rejected = capability_service.reject_action(
            db, owner_id=owner_id, request_id=request_id, decided_by=owner_id, note=note
        )
        rejected["replan"] = await _replan_after_rejection(db, owner_id=owner_id, approval=rejected, note=note)
        return rejected

    approved = capability_service.approve_action(
        db, owner_id=owner_id, request_id=request_id, decided_by=owner_id, note=note
    )
    return await _execute(db, owner_id=owner_id, approval=approved)


async def _execute(db: Session, *, owner_id: str, approval: dict) -> dict:
    """Run an approved action through its registered executor. A missing
    executor is not an error — it means consent is recorded and the action is
    waiting on the integration that will eventually perform it."""
    try:
        executed = await capability_executors.execute_if_registered(db, owner_id=owner_id, approval=approval)
    except Exception as exc:  # noqa: BLE001 - surfaced, not swallowed
        logger.error("approval_execution_failed", request_id=approval["id"], error=str(exc))
        approval["execution_error"] = str(exc)
        return approval
    if executed is None:
        approval["executed"] = False
        approval["execution_note"] = (
            f"Approved. '{approval['capability_name']}' has no automatic executor registered, "
            "so nothing was performed against an external service."
        )
        return approval
    executed["executed"] = True
    return executed


async def decide_plan(
    db: Session, *, owner_id: str, group_id: str, approve: bool, note: str | None = None
) -> dict:
    """Decide a WHOLE plan. Approving runs its pending steps in sequence,
    stopping at the first execution failure so the rest of the plan doesn't
    proceed on a broken assumption. Steps already decided are left alone."""
    rows = _plan_rows(db, owner_id=owner_id, group_id=group_id)
    results: list[dict] = []
    stopped_at: str | None = None

    for row in rows:
        if row.status != "pending":
            continue
        outcome = await decide(db, owner_id=owner_id, request_id=row.id, approve=approve, note=note)
        results.append(outcome)
        if approve and outcome.get("execution_error"):
            stopped_at = row.id
            break

    return {
        "group_id": group_id,
        "decided": len(results),
        "stopped_at": stopped_at,
        "steps": results,
        "queue": queue(db, owner_id=owner_id, company_id=rows[0].company_id),
    }


async def _replan_after_rejection(db: Session, *, owner_id: str, approval: dict, note: str | None) -> dict | None:
    """A rejection is information, not a dead end: hand it back to whatever
    planned the step so the rest of the plan can adapt. Only the Work Queue
    plans multi-step work today, so only it can re-plan; a standalone rejected
    action simply stays rejected."""
    if approval["capability_name"] != "work_queue":
        return None
    payload = approval.get("payload") or {}
    run_id = payload.get("run_id")
    if not run_id:
        return None
    try:
        from app.core import work_queue_service  # local import avoids an import cycle

        return await work_queue_service.replan_after_rejection(
            db,
            owner_id=owner_id,
            run_id=run_id,
            subtask_id=payload.get("subtask_id"),
            rejection_note=note,
        )
    except Exception as exc:  # noqa: BLE001 - re-planning is a bonus, never a blocker
        logger.error("replan_failed", run_id=run_id, error=str(exc))
        return None


def history(db: Session, *, owner_id: str, company_id: str | None = None, limit: int = 50) -> list[dict]:
    """Everything already decided, newest first — the workspace's approval
    record. Reads from the same rows the queue does, so nothing can drift."""
    q = db.query(ApprovalRequest).filter(
        ApprovalRequest.owner_id == owner_id, ApprovalRequest.status != "pending"
    )
    if company_id:
        q = q.filter(ApprovalRequest.company_id == company_id)
    rows = q.order_by(ApprovalRequest.decided_at.desc().nullslast()).limit(limit).all()
    return [capability_service.serialize_approval(r) for r in rows]


def request_audit(db: Session, *, owner_id: str, request_id: str) -> list[dict]:
    """The full trail for ONE request — proposed, edited, approved/rejected,
    executed — so the record behind a decision is visible next to it rather
    than buried in a global log."""
    _owned(db, request_id, owner_id)  # ownership check before reading its trail
    rows = (
        db.query(CapabilityAuditLog)
        .filter(
            CapabilityAuditLog.owner_id == owner_id,
            CapabilityAuditLog.approval_request_id == request_id,
        )
        .order_by(CapabilityAuditLog.created_at.asc())
        .all()
    )
    return [capability_service.serialize_audit(r) for r in rows]


def plan_progress(steps: list[dict]) -> dict:
    """Small helper the UI and tests share, so 'is this plan done' is defined
    once rather than reimplemented per surface."""
    return {
        "total": len(steps),
        "pending": sum(1 for s in steps if s["status"] == "pending"),
        "done": sum(1 for s in steps if s["status"] in DONE_STATES),
    }


def parse_risks(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (TypeError, ValueError):
        return []
