"""
HTTP surface for the Capability framework — company-scoped enable/disable
and permissions, health checks, the approval queue, and scheduled jobs.
See app.core.capability_service for the actual logic; this file only shapes
requests/responses, the same discipline as api/v1/endpoints/memory.py.

Three routers, one per concern, all mounted here: capabilities (config +
health), approvals (the human-in-the-loop queue), scheduled-jobs
(background agents' data model).
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import capability_executors, capability_service

# Aliased: a route handler below is also named `get_capability` (the GET
# /{name} endpoint) — without the alias, that later `def get_capability`
# rebinds the module-global name and _capability_view's call to the
# imported registry function silently starts calling the route handler
# instead (wrong signature -> unhandled 500) the moment Python finishes
# loading this module.
from app.core.capabilities_registry import CAPABILITIES, get_capability as get_capability_def
from app.db.session import get_db

capabilities_router = APIRouter(prefix="/capabilities", tags=["capabilities"])
approvals_router = APIRouter(prefix="/approvals", tags=["approvals"])
scheduled_jobs_router = APIRouter(prefix="/scheduled-jobs", tags=["scheduled-jobs"])


def _capability_view(db: Session, owner_id: str, name: str, company_id: str | None) -> dict:
    # get_capability_def() raises the app's own ValidationError (-> 422) for
    # an unknown name; indexing CAPABILITIES directly here would instead
    # raise a raw KeyError and surface as an unhandled 500.
    capability_def = get_capability_def(name)
    cfg = capability_service.get_capability_config(db, owner_id=owner_id, capability_name=name, company_id=company_id)
    return {
        "name": name,
        "description": capability_def.description,
        "integration_name": capability_def.integration_name,
        "actions": [
            {"name": a.name, "description": a.description, "requires_approval": a.requires_approval}
            for a in capability_def.actions
        ],
        **cfg,
    }


class CapabilityConfigUpdate(BaseModel):
    company_id: str | None = None
    enabled: bool | None = None
    permissions: list[str] | None = None


class ApprovalCreate(BaseModel):
    capability_name: str
    action_type: str
    payload: dict = {}
    company_id: str | None = None


class ApprovalDecision(BaseModel):
    note: str | None = None


class ExecutedReport(BaseModel):
    note: str | None = None


class ScheduledJobCreate(BaseModel):
    capability_name: str
    action_type: str
    schedule_cron: str
    payload: dict | None = None
    company_id: str | None = None


class ScheduledJobUpdate(BaseModel):
    enabled: bool


# --- Capabilities: config + health --------------------------------------


@capabilities_router.get("")
def list_capabilities(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = Query(None, description="Real company id, or omit for the account-wide default."),
):
    return [_capability_view(db, current_user.id, name, company_id) for name in CAPABILITIES]


@capabilities_router.get("/audit-log")
def audit_log(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    capability_name: str | None = Query(None),
    company_id: str | None = Query("any", description="'any', omit for account-wide, or a real company id."),
    limit: int = Query(50, le=200),
):
    return capability_service.get_audit_log(
        db, owner_id=current_user.id, capability_name=capability_name, company_id=company_id, limit=limit
    )


@capabilities_router.get("/{name}")
def get_capability(
    name: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = Query(None),
):
    return _capability_view(db, current_user.id, name, company_id)


@capabilities_router.put("/{name}/config")
def update_capability_config(
    name: str, payload: CapabilityConfigUpdate, current_user: CurrentUser, db: Session = Depends(get_db)
):
    if payload.enabled is not None:
        capability_service.set_capability_enabled(
            db, owner_id=current_user.id, capability_name=name, enabled=payload.enabled, company_id=payload.company_id
        )
    if payload.permissions is not None:
        capability_service.set_capability_permissions(
            db,
            owner_id=current_user.id,
            capability_name=name,
            permissions=payload.permissions,
            company_id=payload.company_id,
        )
    return _capability_view(db, current_user.id, name, payload.company_id)


@capabilities_router.post("/{name}/health-check")
async def health_check(
    name: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = Query(None),
):
    return await capability_service.run_health_check(
        db, owner_id=current_user.id, capability_name=name, company_id=company_id
    )


# --- Approvals: the human-in-the-loop queue ------------------------------


@approvals_router.get("")
def list_approvals(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = Query("any"),
    status: str | None = Query(None),
):
    return capability_service.list_approvals(db, owner_id=current_user.id, company_id=company_id, status=status)


@approvals_router.post("", status_code=201)
def create_approval(payload: ApprovalCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    """Propose a side-effecting action for human review. In production this
    is normally called in-process by an integration (e.g. Gmail's send_email
    handler) rather than hit directly, but it's a real, permanent entry
    point — also useful for a future 'ask Jarvis to do X, pending my
    approval' manual flow."""
    return capability_service.propose_action(
        db,
        owner_id=current_user.id,
        capability_name=payload.capability_name,
        action_type=payload.action_type,
        payload=payload.payload,
        company_id=payload.company_id,
        requested_by=current_user.id,
    )


@approvals_router.post("/{request_id}/approve")
async def approve(
    request_id: str, payload: ApprovalDecision, current_user: CurrentUser, db: Session = Depends(get_db)
):
    """Approves the request, then immediately attempts execution if this
    capability has a registered executor (Gmail does — see
    app.core.gmail_service). If execution fails (external API rejects the
    call, credential revoked, ...), the exception propagates as a normal
    error response and the request is left in 'approved' rather than
    silently marked executed for something that didn't actually happen."""
    approved = capability_service.approve_action(
        db, owner_id=current_user.id, request_id=request_id, decided_by=current_user.id, note=payload.note
    )
    executed = await capability_executors.execute_if_registered(db, owner_id=current_user.id, approval=approved)
    return executed or approved


@approvals_router.post("/{request_id}/reject")
def reject(
    request_id: str, payload: ApprovalDecision, current_user: CurrentUser, db: Session = Depends(get_db)
):
    return capability_service.reject_action(
        db, owner_id=current_user.id, request_id=request_id, decided_by=current_user.id, note=payload.note
    )


@approvals_router.post("/{request_id}/executed")
def mark_executed(
    request_id: str, payload: ExecutedReport, current_user: CurrentUser, db: Session = Depends(get_db)
):
    """Called by whatever performed the approved action against the real
    external API (the integration code itself, once it exists) to close
    the loop — kept as its own endpoint since approval and execution can
    happen at different times."""
    return capability_service.mark_executed(
        db, owner_id=current_user.id, request_id=request_id, result_note=payload.note
    )


# --- Scheduled jobs: background agents' data model -----------------------


@scheduled_jobs_router.get("")
def list_scheduled_jobs(
    current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query("any")
):
    return capability_service.list_scheduled_jobs(db, owner_id=current_user.id, company_id=company_id)


@scheduled_jobs_router.post("", status_code=201)
def create_scheduled_job(payload: ScheduledJobCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    return capability_service.create_scheduled_job(
        db,
        owner_id=current_user.id,
        capability_name=payload.capability_name,
        action_type=payload.action_type,
        schedule_cron=payload.schedule_cron,
        payload=payload.payload,
        company_id=payload.company_id,
    )


@scheduled_jobs_router.put("/{job_id}")
def update_scheduled_job(
    job_id: str, payload: ScheduledJobUpdate, current_user: CurrentUser, db: Session = Depends(get_db)
):
    return capability_service.set_scheduled_job_enabled(
        db, owner_id=current_user.id, job_id=job_id, enabled=payload.enabled
    )


@scheduled_jobs_router.delete("/{job_id}", status_code=204)
def delete_scheduled_job(job_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    capability_service.delete_scheduled_job(db, owner_id=current_user.id, job_id=job_id)
