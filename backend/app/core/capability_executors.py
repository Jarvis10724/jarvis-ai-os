"""
Pluggable execution hooks for approved capability actions.

capability_service.approve_action() only flips an ApprovalRequest to
'approved' — it deliberately knows nothing about Gmail, Shopify, or any
other external API. Actually calling out and then marking the request
'executed' is each capability's own job, registered here by name. A
capability with no executor registered yet (everything except Gmail, for
now) simply stays 'approved' until something finishes the loop — exactly
what capability_service was already built to support, unchanged.
"""
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.core import capability_service

# (db, *, owner_id, company_id, action_type, payload) -> result dict
Executor = Callable[..., Awaitable[dict]]

_EXECUTORS: dict[str, Executor] = {}


def register_executor(capability_name: str, fn: Executor) -> None:
    _EXECUTORS[capability_name] = fn


async def execute_if_registered(db: Session, *, owner_id: str, approval: dict) -> dict | None:
    """`approval` is the serialized ApprovalRequest (capability_service.
    serialize_approval's shape) returned by approve_action(). Returns the
    mark_executed() result if an executor ran and succeeded, or None if
    this capability has no executor yet — callers should fall back to
    returning the plain 'approved' response in that case.

    If the executor raises (the external API rejects the call, the
    credential was revoked, etc.), the exception propagates and the
    request is left in 'approved' — a real, valid resting state the
    framework already supports; nothing here silently swallows a failure
    or fabricates an 'executed' row for a call that didn't happen."""
    executor = _EXECUTORS.get(approval["capability_name"])
    if executor is None:
        return None
    result = await executor(
        db,
        owner_id=owner_id,
        company_id=approval["company_id"],
        action_type=approval["action_type"],
        # `_approval_id` lets an executor tie its own audit record back to the
        # approval that authorized it. Executors ignore keys they don't use.
        payload={**(approval["payload"] or {}), "_approval_id": approval["id"]},
    )
    return capability_service.mark_executed(
        db, owner_id=owner_id, request_id=approval["id"], result_note=str(result)[:500]
    )
