"""
The read/write funnel every Capability (Gmail, Calendar, Shopify,
QuickBooks, Amazon, ...) goes through — same discipline as
app.core.memory_service: ownership checked before every write, an audit row
written after every write, callers never touch the tables directly.

What lives here so no individual integration has to rebuild it:

  - Company-scoped enable/disable and permissions (`get_capability_config`,
    `set_capability_enabled`, `set_capability_permissions`).
  - The approval gate for side-effecting actions (`propose_action`,
    `approve_action`, `reject_action`, `mark_executed`) — see
    app.core.capabilities_registry for which actions require it.
  - A matching, lighter check for read-only actions
    (`authorize_direct_action`) — no approval needed, but still company-
    isolated and permission-gated. Callers execute the real API call
    themselves right after this returns, then call `log_capability_action`.
  - Audit logging for everything above (`get_audit_log`).
  - Health checks (`run_health_check`) — calls the existing
    BaseIntegration.is_connected() through app.integrations.registry and
    caches the result on the capability's config row, so the UI doesn't
    have to hit the external API on every page load.
  - Scheduled jobs (`create_scheduled_job` and friends) — the data half of
    background agents; the dispatch loop that actually runs due jobs is
    built alongside the first capability that needs one, but
    `list_due_scheduled_jobs` is ready for it now.

A brand-new capability (say, 3b's Google Calendar) should only ever need to:
add an entry to capabilities_registry.CAPABILITIES, implement the real
BaseIntegration subclass, and call authorize_direct_action/propose_action
around its reads/writes. Nothing here is capability-specific.
"""
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.capabilities_registry import CAPABILITIES, CapabilityDefinition, get_capability
from app.db.models.capability import (
    APPROVAL_STATUSES,
    ApprovalRequest,
    CapabilityAuditLog,
    CapabilityConfig,
    ScheduledJob,
)
from app.db.models.company import Company
from app.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.logging_config import get_logger

logger = get_logger(__name__)


def _assert_company_owned(db: Session, company_id: str, owner_id: str) -> None:
    exists = db.query(Company.id).filter(Company.id == company_id, Company.owner_id == owner_id).first()
    if not exists:
        raise NotFoundError(f"Company '{company_id}' not found (or it isn't yours).")


def _action_def(capability_def: CapabilityDefinition, action_type: str):
    try:
        return capability_def.action(action_type)
    except KeyError:
        raise ValidationError(
            f"Unknown action '{action_type}' for capability '{capability_def.name}'. "
            f"Valid: {[a.name for a in capability_def.actions]}"
        )


def _write_audit(
    db: Session,
    *,
    owner_id: str,
    capability_name: str,
    action: str,
    company_id: str | None = None,
    approval_request_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    note: str | None = None,
) -> None:
    db.add(
        CapabilityAuditLog(
            owner_id=owner_id,
            company_id=company_id,
            capability_name=capability_name,
            approval_request_id=approval_request_id,
            action=action,
            before_json=json.dumps(before) if before is not None else None,
            after_json=json.dumps(after) if after is not None else None,
            note=note,
        )
    )
    db.commit()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def serialize_config(cfg: CapabilityConfig, capability_def: CapabilityDefinition) -> dict:
    permissions = json.loads(cfg.permissions_json) if cfg.permissions_json else capability_def.default_permissions
    return {
        "id": cfg.id,
        "capability_name": cfg.capability_name,
        "company_id": cfg.company_id,
        "enabled": cfg.enabled,
        "permissions": permissions,
        "config": json.loads(cfg.config_json) if cfg.config_json else None,
        "health_status": cfg.health_status,
        "health_message": cfg.health_message,
        "last_health_check_at": cfg.last_health_check_at.isoformat() if cfg.last_health_check_at else None,
    }


def _default_config_view(capability_name: str, company_id: str | None, capability_def: CapabilityDefinition) -> dict:
    """A config that's never been written yet — shown as the effective
    default rather than lazily creating a DB row just to answer a GET."""
    return {
        "id": None,
        "capability_name": capability_name,
        "company_id": company_id,
        "enabled": True,
        "permissions": capability_def.default_permissions,
        "config": None,
        "health_status": "unknown",
        "health_message": None,
        "last_health_check_at": None,
    }


def serialize_approval(req: ApprovalRequest) -> dict:
    return {
        "id": req.id,
        "capability_name": req.capability_name,
        "company_id": req.company_id,
        "project_id": req.project_id,
        "action_type": req.action_type,
        "payload": json.loads(req.payload_json) if req.payload_json else None,
        "status": req.status,
        "requested_by": req.requested_by,
        "decided_by": req.decided_by,
        "decided_at": req.decided_at.isoformat() if req.decided_at else None,
        "executed_at": req.executed_at.isoformat() if req.executed_at else None,
        "note": req.note,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }


def serialize_audit(row: CapabilityAuditLog) -> dict:
    return {
        "id": row.id,
        "capability_name": row.capability_name,
        "company_id": row.company_id,
        "approval_request_id": row.approval_request_id,
        "action": row.action,
        "before": json.loads(row.before_json) if row.before_json else None,
        "after": json.loads(row.after_json) if row.after_json else None,
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_job(job: ScheduledJob) -> dict:
    return {
        "id": job.id,
        "capability_name": job.capability_name,
        "company_id": job.company_id,
        "action_type": job.action_type,
        "payload": json.loads(job.payload_json) if job.payload_json else {},
        "schedule_cron": job.schedule_cron,
        "enabled": job.enabled,
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
        "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
    }


# ---------------------------------------------------------------------------
# Capability config — company-scoped enable/disable + permissions
# ---------------------------------------------------------------------------


def _find_config(db: Session, owner_id: str, capability_name: str, company_id: str | None) -> CapabilityConfig | None:
    q = db.query(CapabilityConfig).filter(
        CapabilityConfig.owner_id == owner_id, CapabilityConfig.capability_name == capability_name
    )
    q = q.filter(CapabilityConfig.company_id.is_(None)) if company_id is None else q.filter(
        CapabilityConfig.company_id == company_id
    )
    return q.first()


def _get_or_create_config(db: Session, owner_id: str, capability_name: str, company_id: str | None) -> CapabilityConfig:
    cfg = _find_config(db, owner_id, capability_name, company_id)
    if cfg:
        return cfg
    cfg = CapabilityConfig(
        owner_id=owner_id, company_id=company_id, capability_name=capability_name, enabled=True, health_status="unknown"
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def get_capability_config(db: Session, *, owner_id: str, capability_name: str, company_id: str | None = None) -> dict:
    capability_def = get_capability(capability_name)
    cfg = _find_config(db, owner_id, capability_name, company_id)
    if cfg is None:
        return _default_config_view(capability_name, company_id, capability_def)
    return serialize_config(cfg, capability_def)


def list_capability_configs(db: Session, *, owner_id: str, company_id: str | None = None) -> list[dict]:
    """One row per known capability for a given scope (real company id or
    account-wide/None) — defaults filled in for anything never configured."""
    return [
        get_capability_config(db, owner_id=owner_id, capability_name=name, company_id=company_id)
        for name in CAPABILITIES
    ]


def set_capability_enabled(
    db: Session, *, owner_id: str, capability_name: str, enabled: bool, company_id: str | None = None
) -> dict:
    capability_def = get_capability(capability_name)
    if company_id:
        _assert_company_owned(db, company_id, owner_id)
    cfg = _get_or_create_config(db, owner_id, capability_name, company_id)
    before = serialize_config(cfg, capability_def)
    cfg.enabled = enabled
    db.commit()
    db.refresh(cfg)
    after = serialize_config(cfg, capability_def)
    _write_audit(
        db,
        owner_id=owner_id,
        company_id=company_id,
        capability_name=capability_name,
        action="enabled" if enabled else "disabled",
        before=before,
        after=after,
    )
    return after


def set_capability_permissions(
    db: Session, *, owner_id: str, capability_name: str, permissions: list[str], company_id: str | None = None
) -> dict:
    capability_def = get_capability(capability_name)
    valid_names = {a.name for a in capability_def.actions}
    unknown = sorted(set(permissions) - valid_names)
    if unknown:
        raise ValidationError(f"Unknown action(s) for '{capability_name}': {unknown}")
    if company_id:
        _assert_company_owned(db, company_id, owner_id)
    cfg = _get_or_create_config(db, owner_id, capability_name, company_id)
    before = serialize_config(cfg, capability_def)
    cfg.permissions_json = json.dumps(permissions)
    db.commit()
    db.refresh(cfg)
    after = serialize_config(cfg, capability_def)
    _write_audit(
        db,
        owner_id=owner_id,
        company_id=company_id,
        capability_name=capability_name,
        action="permissions_changed",
        before=before,
        after=after,
    )
    return after


def is_action_permitted(cfg: CapabilityConfig | None, capability_def: CapabilityDefinition, action_name: str) -> bool:
    if cfg is None or cfg.permissions_json is None:
        return action_name in capability_def.default_permissions
    return action_name in json.loads(cfg.permissions_json)


# ---------------------------------------------------------------------------
# Direct (read-only) actions — no approval, but still gated + audited
# ---------------------------------------------------------------------------


def authorize_direct_action(
    db: Session, *, owner_id: str, capability_name: str, action_type: str, company_id: str | None = None
) -> None:
    """Raises if this action isn't allowed. Callers run the real API call
    themselves right after this returns cleanly, then call
    log_capability_action() to record what happened."""
    capability_def = get_capability(capability_name)
    action_def = _action_def(capability_def, action_type)
    if action_def.requires_approval:
        raise ValidationError(
            f"Action '{action_type}' on '{capability_name}' requires approval — use propose_action(), not authorize_direct_action()."
        )
    if company_id:
        _assert_company_owned(db, company_id, owner_id)
    cfg = _find_config(db, owner_id, capability_name, company_id)
    if cfg is not None and not cfg.enabled:
        raise AuthorizationError(f"Capability '{capability_name}' is disabled for this company.")
    if not is_action_permitted(cfg, capability_def, action_type):
        raise AuthorizationError(f"Action '{action_type}' is not permitted for '{capability_name}' in this company.")


def log_capability_action(
    db: Session,
    *,
    owner_id: str,
    capability_name: str,
    action_type: str,
    company_id: str | None = None,
    note: str | None = None,
    result: dict | None = None,
) -> dict:
    """Written by the caller after actually performing a direct (read-only)
    action — keeps the 'what did Jarvis just do' answer uniform whether the
    action was approval-gated or not."""
    get_capability(capability_name)
    after = {"action_type": action_type, **(result or {})}
    _write_audit(
        db,
        owner_id=owner_id,
        company_id=company_id,
        capability_name=capability_name,
        action="read",
        after=after,
        note=note,
    )
    return {"logged": True}


# ---------------------------------------------------------------------------
# Approval-gated (side-effecting) actions
# ---------------------------------------------------------------------------


def propose_action(
    db: Session,
    *,
    owner_id: str,
    capability_name: str,
    action_type: str,
    payload: dict,
    company_id: str | None = None,
    project_id: str | None = None,
    requested_by: str | None = None,
) -> dict:
    capability_def = get_capability(capability_name)
    action_def = _action_def(capability_def, action_type)
    if not action_def.requires_approval:
        raise ValidationError(
            f"Action '{action_type}' on '{capability_name}' doesn't require approval — "
            "call authorize_direct_action() instead."
        )
    if company_id:
        _assert_company_owned(db, company_id, owner_id)
    cfg = _find_config(db, owner_id, capability_name, company_id)
    if cfg is not None and not cfg.enabled:
        raise AuthorizationError(f"Capability '{capability_name}' is disabled for this company.")
    if not is_action_permitted(cfg, capability_def, action_type):
        raise AuthorizationError(f"Action '{action_type}' is not permitted for '{capability_name}' in this company.")

    req = ApprovalRequest(
        owner_id=owner_id,
        company_id=company_id,
        project_id=project_id,
        capability_name=capability_name,
        action_type=action_type,
        payload_json=json.dumps(payload),
        status="pending",
        requested_by=requested_by or owner_id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    _write_audit(
        db,
        owner_id=owner_id,
        company_id=company_id,
        capability_name=capability_name,
        approval_request_id=req.id,
        action="proposed",
        after=serialize_approval(req),
    )
    return serialize_approval(req)


def _approval_owned(db: Session, request_id: str, owner_id: str) -> ApprovalRequest:
    req = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.id == request_id, ApprovalRequest.owner_id == owner_id)
        .first()
    )
    if not req:
        raise NotFoundError(f"Approval request '{request_id}' not found (or it isn't yours).")
    return req


def _record_approval_timeline(db: Session, req: ApprovalRequest, *, decision: str, note: str | None) -> None:
    """When an approval tied to a Project is decided, log it on that project's
    Timeline. Best-effort and lazily imported so a timeline hiccup never blocks
    the decision itself, and so capability_service stays free of an import-time
    dependency on project_service."""
    if not req.project_id:
        return
    try:
        from app.core import project_service  # local import avoids an import cycle
        from app.db.models.project import Project

        project = db.query(Project).filter(Project.id == req.project_id).first()
        if not project:
            return
        project_service.record_project_event(
            db,
            project=project,
            owner_id=req.owner_id,
            kind="approval_decided",
            title=f"Approval {decision}: {req.capability_name} · {req.action_type}",
            source=req.capability_name,
            detail=note or None,
            ref_id=req.id,
        )
    except Exception as exc:  # noqa: BLE001 - never let timeline logging break a decision
        logger.error("approval_timeline_failed", request_id=req.id, error=str(exc))


def approve_action(db: Session, *, owner_id: str, request_id: str, decided_by: str | None = None, note: str | None = None) -> dict:
    req = _approval_owned(db, request_id, owner_id)
    if req.status != "pending":
        raise ValidationError(f"Approval request is '{req.status}', not pending.")
    before = serialize_approval(req)
    req.status = "approved"
    req.decided_by = decided_by or owner_id
    req.decided_at = datetime.now(timezone.utc)
    if note:
        req.note = note
    db.commit()
    db.refresh(req)
    after = serialize_approval(req)
    _write_audit(
        db,
        owner_id=owner_id,
        company_id=req.company_id,
        capability_name=req.capability_name,
        approval_request_id=req.id,
        action="approved",
        before=before,
        after=after,
        note=note,
    )
    _record_approval_timeline(db, req, decision="approved", note=note)
    return after


def reject_action(db: Session, *, owner_id: str, request_id: str, decided_by: str | None = None, note: str | None = None) -> dict:
    req = _approval_owned(db, request_id, owner_id)
    if req.status != "pending":
        raise ValidationError(f"Approval request is '{req.status}', not pending.")
    before = serialize_approval(req)
    req.status = "rejected"
    req.decided_by = decided_by or owner_id
    req.decided_at = datetime.now(timezone.utc)
    if note:
        req.note = note
    db.commit()
    db.refresh(req)
    after = serialize_approval(req)
    _write_audit(
        db,
        owner_id=owner_id,
        company_id=req.company_id,
        capability_name=req.capability_name,
        approval_request_id=req.id,
        action="rejected",
        before=before,
        after=after,
        note=note,
    )
    _record_approval_timeline(db, req, decision="rejected", note=note)
    return after


def mark_executed(db: Session, *, owner_id: str, request_id: str, result_note: str | None = None) -> dict:
    """Called by the integration after it actually performs the approved
    action against the external API. Kept separate from approve_action()
    because approval and execution can legitimately happen at different
    times (e.g. approved now, executed by a retry a minute later)."""
    req = _approval_owned(db, request_id, owner_id)
    if req.status != "approved":
        raise ValidationError(f"Only approved requests can be marked executed (this one is '{req.status}').")
    before = serialize_approval(req)
    req.status = "executed"
    req.executed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    after = serialize_approval(req)
    _write_audit(
        db,
        owner_id=owner_id,
        company_id=req.company_id,
        capability_name=req.capability_name,
        approval_request_id=req.id,
        action="executed",
        before=before,
        after=after,
        note=result_note,
    )
    return after


def list_approvals(
    db: Session,
    *,
    owner_id: str,
    company_id: str | None = "any",
    project_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    q = db.query(ApprovalRequest).filter(ApprovalRequest.owner_id == owner_id)
    if company_id == "any":
        pass
    elif company_id is None:
        q = q.filter(ApprovalRequest.company_id.is_(None))
    else:
        q = q.filter(ApprovalRequest.company_id == company_id)
    if project_id:
        q = q.filter(ApprovalRequest.project_id == project_id)
    if status:
        if status not in APPROVAL_STATUSES:
            raise ValidationError(f"Unknown status '{status}'. Valid: {', '.join(APPROVAL_STATUSES)}")
        q = q.filter(ApprovalRequest.status == status)
    rows = q.order_by(ApprovalRequest.created_at.desc()).all()
    return [serialize_approval(r) for r in rows]


def get_audit_log(
    db: Session, *, owner_id: str, capability_name: str | None = None, company_id: str | None = "any", limit: int = 50
) -> list[dict]:
    q = db.query(CapabilityAuditLog).filter(CapabilityAuditLog.owner_id == owner_id)
    if capability_name:
        q = q.filter(CapabilityAuditLog.capability_name == capability_name)
    if company_id == "any":
        pass
    elif company_id is None:
        q = q.filter(CapabilityAuditLog.company_id.is_(None))
    else:
        q = q.filter(CapabilityAuditLog.company_id == company_id)
    rows = q.order_by(CapabilityAuditLog.created_at.desc()).limit(limit).all()
    return [serialize_audit(r) for r in rows]


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------


async def run_health_check(db: Session, *, owner_id: str, capability_name: str, company_id: str | None = None) -> dict:
    """Calls the underlying BaseIntegration.is_connected() (if the real
    integration class exists yet — capabilities can be registered ahead of
    their implementation, see capabilities_registry) and caches the result
    on this capability's config row rather than hitting the external API on
    every page load."""
    from app.core import credential_store
    from app.exceptions import IntegrationError
    from app.integrations.registry import get_integration

    capability_def = get_capability(capability_name)
    if company_id:
        _assert_company_owned(db, company_id, owner_id)

    # Must go through credential_store, not a raw IntegrationCredential
    # query — tokens are encrypted at rest, and only credential_store
    # decrypts them. Reading the row directly here would hand
    # get_integration() ciphertext instead of a usable access token.
    credentials = (
        credential_store.load_credentials(
            db, owner_id=owner_id, company_id=company_id, provider=capability_def.integration_name
        )
        or {}
    )

    try:
        integration = get_integration(capability_def.integration_name, credentials=credentials)
        connected = await integration.is_connected()
        status = "ok" if connected else "disconnected"
        message = None
    except IntegrationError as exc:
        status, message = "error", str(exc)
    except Exception as exc:  # noqa: BLE001 — a broken integration shouldn't 500 the health-check endpoint
        status, message = "error", str(exc)

    cfg = _get_or_create_config(db, owner_id, capability_name, company_id)
    before = serialize_config(cfg, capability_def)
    cfg.health_status = status
    cfg.health_message = message
    cfg.last_health_check_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cfg)
    after = serialize_config(cfg, capability_def)
    _write_audit(
        db,
        owner_id=owner_id,
        company_id=company_id,
        capability_name=capability_name,
        action="health_check",
        before=before,
        after=after,
        note=message,
    )
    return after


# ---------------------------------------------------------------------------
# Scheduled jobs — data model for background agents
# ---------------------------------------------------------------------------


def create_scheduled_job(
    db: Session,
    *,
    owner_id: str,
    capability_name: str,
    action_type: str,
    schedule_cron: str,
    payload: dict | None = None,
    company_id: str | None = None,
) -> dict:
    capability_def = get_capability(capability_name)
    _action_def(capability_def, action_type)
    if company_id:
        _assert_company_owned(db, company_id, owner_id)
    cfg = _find_config(db, owner_id, capability_name, company_id)
    if cfg is not None and not cfg.enabled:
        raise AuthorizationError(f"Capability '{capability_name}' is disabled for this company.")
    if not is_action_permitted(cfg, capability_def, action_type):
        raise AuthorizationError(f"Action '{action_type}' isn't permitted for '{capability_name}' — grant it before scheduling.")

    job = ScheduledJob(
        owner_id=owner_id,
        company_id=company_id,
        capability_name=capability_name,
        action_type=action_type,
        payload_json=json.dumps(payload or {}),
        schedule_cron=schedule_cron,
        enabled=True,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    _write_audit(
        db,
        owner_id=owner_id,
        company_id=company_id,
        capability_name=capability_name,
        action="scheduled",
        after=serialize_job(job),
    )
    return serialize_job(job)


def _job_owned(db: Session, job_id: str, owner_id: str) -> ScheduledJob:
    job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id, ScheduledJob.owner_id == owner_id).first()
    if not job:
        raise NotFoundError(f"Scheduled job '{job_id}' not found (or it isn't yours).")
    return job


def list_scheduled_jobs(db: Session, *, owner_id: str, company_id: str | None = "any") -> list[dict]:
    q = db.query(ScheduledJob).filter(ScheduledJob.owner_id == owner_id)
    if company_id == "any":
        pass
    elif company_id is None:
        q = q.filter(ScheduledJob.company_id.is_(None))
    else:
        q = q.filter(ScheduledJob.company_id == company_id)
    rows = q.order_by(ScheduledJob.created_at.desc()).all()
    return [serialize_job(r) for r in rows]


def set_scheduled_job_enabled(db: Session, *, owner_id: str, job_id: str, enabled: bool) -> dict:
    job = _job_owned(db, job_id, owner_id)
    before = serialize_job(job)
    job.enabled = enabled
    db.commit()
    db.refresh(job)
    after = serialize_job(job)
    _write_audit(
        db,
        owner_id=owner_id,
        company_id=job.company_id,
        capability_name=job.capability_name,
        action="scheduled" if enabled else "unscheduled",
        before=before,
        after=after,
    )
    return after


def delete_scheduled_job(db: Session, *, owner_id: str, job_id: str) -> None:
    job = _job_owned(db, job_id, owner_id)
    before = serialize_job(job)
    db.delete(job)
    db.commit()
    _write_audit(
        db,
        owner_id=owner_id,
        company_id=before["company_id"],
        capability_name=before["capability_name"],
        action="unscheduled",
        before=before,
    )


def list_due_scheduled_jobs(db: Session, *, now: datetime | None = None) -> list[ScheduledJob]:
    """Not owner-scoped — meant to be called by a background dispatch loop
    (not yet built; lands with the first capability that needs one), which
    acts across every user's jobs rather than on behalf of one HTTP request.
    A null `next_run_at` counts as due (never scheduled yet)."""
    now = now or datetime.now(timezone.utc)
    return (
        db.query(ScheduledJob)
        .filter(ScheduledJob.enabled.is_(True))
        .filter((ScheduledJob.next_run_at.is_(None)) | (ScheduledJob.next_run_at <= now))
        .all()
    )
