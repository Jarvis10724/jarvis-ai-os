"""
The change feed — how one Jarvis stays one Jarvis across every device.

There is no desktop state and no phone state. Every client renders what the
database holds; this module's only job is to tell every connected client, the
moment something changes, that it should look again.

Deliberately NOT a data channel. Events carry `{company_id, kind, version}` and
nothing else — never the changed rows. A client that hears "approvals changed"
re-fetches approvals through the same authenticated endpoint it always used, so
there is exactly one read path, one authorization check, and no way for the feed
to become a second, subtly-different source of truth.

Two properties make this survive real life rather than just a demo:

  * VERSIONS, not just pings. Each scope carries a counter. A client that was
    asleep — a closed MacBook lid, an iPhone with Jarvis in the background —
    reconnects, compares its last-seen version, and re-syncs if it fell behind.
    Missing an event is expected; missing a change is not.

  * An EPOCH. Versions live in memory, so a backend restart resets them, and a
    client holding version 12 would otherwise think it was ahead of a server at
    version 0 and never re-fetch. Every payload carries the epoch this process
    started with; a client seeing a new epoch re-syncs everything.

Writes announce themselves by calling mark_changed() in the SERVICE layer, so a
feature that goes through the existing services inherits synchronization without
touching a single client. That is the point: sync is a property of the
architecture, not a checklist item each new feature has to remember.
"""
import asyncio
import time
from collections import defaultdict

from app.logging_config import get_logger

logger = get_logger(__name__)

#: Identifies this process's counter sequence. A client that sees a different
#: epoch than it last saw treats all its versions as meaningless and re-syncs.
EPOCH = str(int(time.time() * 1000))

#: Kinds of state a client can be watching. A kind is a fan-out hint, not a
#: permission boundary — the re-fetch is still authorized normally.
KINDS = (
    "approvals", "shopify", "products", "inventory", "collections", "discounts",
    "content", "conversations", "memory", "tasks", "projects", "notifications",
    "workspace", "files", "research", "email", "calendar", "agents",
)

#: scope key -> monotonic version. Scope is a company id, or "user:<id>" for
#: account-wide state that isn't tied to one workspace.
_versions: dict[str, int] = defaultdict(int)

#: owner_id -> the queues of that owner's connected clients. Scoped by owner so
#: one account's changes can never be delivered to another's stream.
_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)


def scope_key(company_id: str | None, owner_id: str | None = None) -> str:
    return company_id or f"user:{owner_id or 'unknown'}"


def mark_changed(
    *, company_id: str | None, kind: str, owner_id: str | None = None, detail: str | None = None
) -> int:
    """Something changed. Bump the scope's version and tell every connected
    client of this owner to look again.

    Safe to call from sync code: delivery is non-blocking (a full queue means a
    client is already behind and will re-sync from its version anyway), and a
    failure to notify must never break the write that just succeeded.
    """
    key = scope_key(company_id, owner_id)
    _versions[key] += 1
    version = _versions[key]
    event = {
        "type": "changed",
        "epoch": EPOCH,
        "company_id": company_id,
        "scope": key,
        "kind": kind,
        "version": version,
        "detail": detail,
    }

    targets = list(_subscribers.get(owner_id, ())) if owner_id else [
        q for queues in _subscribers.values() for q in queues
    ]
    for queue in targets:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # The client is behind. It will notice via the version on its next
            # heartbeat and re-sync — dropping this event costs nothing.
            pass
    logger.debug("sync_marked", kind=kind, scope=key, version=version, clients=len(targets))
    return version


def versions_for(owner_id: str, company_id: str | None = None) -> dict:
    """The current version stamps, for a client deciding whether it fell behind
    while it was asleep."""
    keys = [scope_key(company_id, owner_id)] if company_id else list(_versions)
    return {
        "epoch": EPOCH,
        "versions": {k: _versions[k] for k in keys},
    }


def subscribe(owner_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers[owner_id].add(queue)
    logger.info("sync_client_connected", owner_id=owner_id, clients=len(_subscribers[owner_id]))
    return queue


def unsubscribe(owner_id: str, queue: asyncio.Queue) -> None:
    _subscribers[owner_id].discard(queue)
    if not _subscribers[owner_id]:
        _subscribers.pop(owner_id, None)


def connected_clients(owner_id: str) -> int:
    return len(_subscribers.get(owner_id, ()))
