"""
Orchestration layer between Calendar's HTTP endpoints and the lower-level
pieces: credential_store (encrypted, company-scoped tokens),
capability_service (the permission/approval/audit gate), and
GoogleCalendarIntegration (the real Calendar API calls). Mirrors
app.core.gmail_service exactly — see that module's docstring for the
shape this follows.

Read (list/get events) executes immediately — see `authorize_direct_action`
calls below. Create/update/delete only ever run through `execute_action`,
called by capability_executors.execute_if_registered() after a human has
approved the corresponding ApprovalRequest; the `propose_*` functions below
only create that pending request; they never touch the Calendar API
themselves.
"""
from datetime import datetime, timezone

from app.core import capability_service, credential_store
from app.core.capability_executors import register_executor
from app.exceptions import ValidationError
from app.integrations.google_calendar_integration import GoogleCalendarIntegration

CAPABILITY_NAME = "google_calendar"


def _load_integration(db, *, owner_id: str, company_id: str | None) -> GoogleCalendarIntegration:
    creds = credential_store.load_credentials(db, owner_id=owner_id, company_id=company_id, provider=CAPABILITY_NAME)
    if not creds or not creds.get("access_token"):
        raise ValidationError("Calendar is not connected for this company yet — connect it from Integrations first.")
    return GoogleCalendarIntegration(credentials=creds)


async def _call(
    db, owner_id: str, company_id: str | None, integration: GoogleCalendarIntegration, method_name: str, **kwargs
):
    """Every real Calendar call goes through here so a refreshed access
    token (GoogleCalendarIntegration._request refreshes in-memory on a 401
    but can't persist it itself — it has no db session) gets written back
    via credential_store exactly once, right after the call that
    triggered it."""
    method = getattr(integration, method_name)
    result = await method(**kwargs)
    if integration.refreshed_access_token:
        credential_store.save_credentials(
            db,
            owner_id=owner_id,
            company_id=company_id,
            provider=CAPABILITY_NAME,
            access_token=integration.refreshed_access_token,
        )
    return result


# ---------------------------------------------------------------------------
# Direct actions — read, no approval needed
# ---------------------------------------------------------------------------


async def list_events(
    db, *, owner_id: str, company_id: str | None, max_results: int = 10, upcoming_only: bool = True
) -> list[dict]:
    """'Next N events' — upcoming_only=True (the default) sets timeMin to
    now so past events never show up in a 'what's next' query; pass False
    to also see a moment-in-time snapshot including already-started
    events on the current day."""
    capability_service.authorize_direct_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="list_events", company_id=company_id
    )
    integration = _load_integration(db, owner_id=owner_id, company_id=company_id)
    time_min = datetime.now(timezone.utc).isoformat() if upcoming_only else None
    result = await _call(db, owner_id, company_id, integration, "list_events", max_results=max_results, time_min=time_min)
    capability_service.log_capability_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="list_events", company_id=company_id,
        result={"count": len(result.data)},
    )
    return result.data


async def get_event(db, *, owner_id: str, company_id: str | None, event_id: str) -> dict:
    capability_service.authorize_direct_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="get_event", company_id=company_id
    )
    integration = _load_integration(db, owner_id=owner_id, company_id=company_id)
    result = await _call(db, owner_id, company_id, integration, "get_event", event_id=event_id)
    capability_service.log_capability_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="get_event", company_id=company_id, note=event_id
    )
    return result.data


# ---------------------------------------------------------------------------
# Approval-gated actions — propose only; execution happens post-approval
# ---------------------------------------------------------------------------


def propose_create_event(
    db, *, owner_id: str, company_id: str | None, summary: str, start: str, end: str,
    description: str = "", location: str = "", attendees: list[str] | None = None, all_day: bool = False,
) -> dict:
    _load_integration(db, owner_id=owner_id, company_id=company_id)  # fail fast if Calendar isn't even connected
    return capability_service.propose_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="create_event",
        payload={
            "summary": summary, "start": start, "end": end, "description": description,
            "location": location, "attendees": attendees or [], "all_day": all_day,
        },
        company_id=company_id,
        requested_by=owner_id,
    )


def propose_update_event(
    db, *, owner_id: str, company_id: str | None, event_id: str, summary: str | None = None,
    start: str | None = None, end: str | None = None, description: str | None = None,
    location: str | None = None, all_day: bool = False,
) -> dict:
    _load_integration(db, owner_id=owner_id, company_id=company_id)
    return capability_service.propose_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="update_event",
        payload={
            "event_id": event_id, "summary": summary, "start": start, "end": end,
            "description": description, "location": location, "all_day": all_day,
        },
        company_id=company_id,
        requested_by=owner_id,
    )


def propose_delete_event(db, *, owner_id: str, company_id: str | None, event_id: str) -> dict:
    _load_integration(db, owner_id=owner_id, company_id=company_id)
    return capability_service.propose_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="delete_event",
        payload={"event_id": event_id},
        company_id=company_id,
        requested_by=owner_id,
    )


async def execute_action(db, *, owner_id: str, company_id: str | None, action_type: str, payload: dict) -> dict:
    """Called only by capability_executors after a human approves the
    ApprovalRequest — never by an HTTP endpoint directly. Dispatches to the
    real Calendar API call for whichever approval-gated action was
    proposed."""
    integration = _load_integration(db, owner_id=owner_id, company_id=company_id)

    if action_type == "create_event":
        result = await _call(
            db, owner_id, company_id, integration, "create_event",
            summary=payload["summary"], start=payload["start"], end=payload["end"],
            description=payload.get("description", ""), location=payload.get("location", ""),
            attendees=payload.get("attendees"), all_day=payload.get("all_day", False),
        )
    elif action_type == "update_event":
        result = await _call(
            db, owner_id, company_id, integration, "update_event",
            event_id=payload["event_id"], summary=payload.get("summary"), start=payload.get("start"),
            end=payload.get("end"), description=payload.get("description"), location=payload.get("location"),
            all_day=payload.get("all_day", False),
        )
    elif action_type == "delete_event":
        result = await _call(db, owner_id, company_id, integration, "delete_event", event_id=payload["event_id"])
    else:
        raise ValidationError(f"Calendar has no executor for action '{action_type}'.")
    return result.data


# Registering here (rather than requiring a separate bootstrap step) means
# simply importing this module — which api/v1/endpoints/calendar.py always
# does — is what wires the executor in.
register_executor(CAPABILITY_NAME, execute_action)
