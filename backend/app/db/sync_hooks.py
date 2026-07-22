"""
The structural guarantee: no write can reach the database without every
connected client being told.

Wiring `sync_service.mark_changed()` into each service by hand works right up
until someone adds a feature and forgets — and a forgotten call is invisible.
It doesn't fail a test or raise an error; the phone is just quietly stale, and
you find out during a demo.

So this listens to the SQLAlchemy Session itself. Any row written through any
session — a service, an endpoint, an agent, a migration script, a feature that
doesn't exist yet — is collected at flush and announced after commit. A new
feature inherits synchronization by virtue of using the database, which is not
something it can opt out of or neglect.

Two details that make it correct rather than merely convenient:

  * Collected at AFTER_FLUSH, emitted at AFTER_COMMIT. Objects are still
    readable at flush time (after commit they're expired), and announcing only
    after commit means a rolled-back transaction never tells anyone a change
    happened that didn't.

  * Never breaks the write. Notification is best-effort; a failure to announce
    is logged, never raised. Losing an event costs a client one stale render
    until the next heartbeat reconciles versions — losing the write would cost
    real data.
"""
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core import sync_service
from app.logging_config import get_logger

logger = get_logger(__name__)

#: Model class name -> the kind of state a client would be displaying. A model
#: absent from this map still syncs, under the catch-all "workspace" kind,
#: because being wrong about WHICH kind changed only costs an extra re-fetch —
#: whereas being silent costs correctness.
KIND_BY_MODEL: dict[str, str] = {
    "ApprovalRequest": "approvals",
    "CapabilityAuditLog": "approvals",
    "CapabilityConfig": "workspace",
    "BrandBrain": "shopify",
    "BrandProduct": "products",
    "BrandCollection": "collections",
    "Product": "products",
    "Company": "workspace",
    "CompanySection": "workspace",
    "Project": "projects",
    "ProjectEvent": "projects",
    "Task": "tasks",
    "MemoryEntry": "memory",
    "MemoryLink": "memory",
    "WorkspaceSession": "conversations",
    "WorkspaceMessage": "conversations",
    "AgentRun": "agents",
    "Client": "workspace",
    "PluginConfig": "workspace",
}

#: Written on every request but never displayed — announcing these would wake
#: every client for nothing.
IGNORED_MODELS = {"OAuthState", "User", "IntegrationCredential"}


def _describe(obj) -> tuple[str, str | None, str | None] | None:
    name = type(obj).__name__
    if name in IGNORED_MODELS:
        return None
    kind = KIND_BY_MODEL.get(name, "workspace")
    company_id = getattr(obj, "company_id", None)
    owner_id = getattr(obj, "owner_id", None)
    # A Company row IS the workspace, so its own id is the scope.
    if name == "Company":
        company_id = getattr(obj, "id", None)
    return kind, company_id, owner_id


@event.listens_for(Session, "after_flush")
def _collect_changes(session: Session, _flush_context) -> None:
    pending: set = session.info.setdefault("_sync_pending", set())
    for obj in (*session.new, *session.dirty, *session.deleted):
        try:
            described = _describe(obj)
        except Exception:  # noqa: BLE001 - never let bookkeeping break a write
            described = None
        if described:
            pending.add(described)


@event.listens_for(Session, "after_commit")
def _emit_changes(session: Session) -> None:
    pending = session.info.pop("_sync_pending", None)
    if not pending:
        return
    for kind, company_id, owner_id in pending:
        try:
            sync_service.mark_changed(
                company_id=company_id, kind=kind, owner_id=owner_id, detail="db"
            )
        except Exception as exc:  # noqa: BLE001
            # The write already succeeded and is safe. A missed announcement
            # self-heals on the next heartbeat's version comparison.
            logger.warning("sync_announce_failed", kind=kind, error=str(exc))


@event.listens_for(Session, "after_rollback")
def _discard_changes(session: Session) -> None:
    """A rolled-back transaction changed nothing, so it announces nothing."""
    session.info.pop("_sync_pending", None)
