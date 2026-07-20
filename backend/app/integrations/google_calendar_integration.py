"""
Google Calendar integration — real REST calls against the Calendar API v3.

Same shape as app.integrations.email_integration: read (list/get events)
executes directly, no approval needed. Create/update/delete only ever run
via app.core.capability_executors after a human approves the corresponding
ApprovalRequest — this class has no opinion about approval, it just does
what it's told. See app.core.capabilities_registry's "google_calendar"
entry for the authoritative list of which action is gated.

Auth: shares the same Google OAuth client (client_id/secret) as Gmail via
app.integrations.google_oauth, but requests its own narrower scopes and is
stored as its own IntegrationCredential row (provider="google_calendar") —
connecting Calendar never touches or requires Gmail's credentials and vice
versa. Same in-memory-refresh-on-401 contract as EmailIntegration: this
class never persists a refreshed access_token itself (no db session here);
app.core.calendar_service does that via `refreshed_access_token`.
"""
import httpx

from app.exceptions import IntegrationError
from app.integrations import google_oauth
from app.integrations.base import BaseIntegration, IntegrationActionResult

CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"

# Narrowest scopes covering the full action set (list/get + create/update/
# delete on events):
#   - calendar.readonly: list/get events.
#   - calendar.events: create/update/delete events on any calendar the user
#     can access — a purpose-built scope for event CRUD. Deliberately NOT
#     the full `calendar` scope, which additionally grants creating/
#     deleting whole calendars and changing calendar-level sharing
#     settings, never needed here.
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


class CalendarAuthError(IntegrationError):
    """A Calendar API call failed with 401 even after a refresh attempt —
    the refresh_token itself is invalid/revoked. Distinct from a generic
    IntegrationError so callers (health checks, capability actions) can
    tell the user 'reconnect Calendar' instead of a generic failure."""

    code = "calendar_auth_error"


class GoogleCalendarIntegration(BaseIntegration):
    name = "google_calendar"
    description = "Google Calendar — view, create, update, and delete events."

    def __init__(self, credentials: dict | None = None):
        super().__init__(credentials)
        # Set by _request() when a 401 forced an in-memory refresh — the
        # caller (app.core.calendar_service) checks this after every call
        # and persists it via credential_store if present. Never read by
        # anything inside this class.
        self.refreshed_access_token: str | None = None

    @staticmethod
    def _auth_header(access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    async def is_connected(self) -> bool:
        """Real connectivity probe (GET the primary calendar), not just 'is
        there a token string'. Attempts an in-memory refresh if the current
        access_token is stale so a merely-expired-but-refreshable token
        still reports connected; a revoked/invalid refresh_token reports
        disconnected. Never persists a refreshed token (no db session
        here) — the next real action call does that via calendar_service."""
        access_token = self.credentials.get("access_token")
        if not access_token:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{CALENDAR_API_BASE}/calendars/primary", headers=self._auth_header(access_token))
            if resp.status_code == 200:
                return True
            if resp.status_code != 401:
                return False
            refresh_token = self.credentials.get("refresh_token")
            if not refresh_token:
                return False
            try:
                token_data = await google_oauth.refresh_access_token(refresh_token=refresh_token, client=client)
            except IntegrationError:
                return False
            retry = await client.get(
                f"{CALENDAR_API_BASE}/calendars/primary", headers=self._auth_header(token_data["access_token"])
            )
            return retry.status_code == 200

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        return google_oauth.build_auth_url(scopes=CALENDAR_SCOPES, redirect_uri=redirect_uri, state=state)

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        return await google_oauth.exchange_code(code=code, redirect_uri=redirect_uri)

    async def _request(
        self, method: str, path: str, *, json_body: dict | None = None, params: dict | None = None
    ) -> dict:
        """Every real Calendar API call funnels through here so the
        401-refresh-and-retry logic lives in exactly one place."""
        access_token = self.credentials.get("access_token")
        if not access_token:
            raise CalendarAuthError("Calendar is not connected (no access token).")

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.request(
                method,
                f"{CALENDAR_API_BASE}{path}",
                headers=self._auth_header(access_token),
                json=json_body,
                params=params,
            )
            if resp.status_code == 401:
                refresh_token = self.credentials.get("refresh_token")
                if not refresh_token:
                    raise CalendarAuthError(
                        "Calendar access token expired and no refresh token is stored — reconnect required."
                    )
                token_data = await google_oauth.refresh_access_token(refresh_token=refresh_token, client=client)
                new_access_token = token_data["access_token"]
                resp = await client.request(
                    method,
                    f"{CALENDAR_API_BASE}{path}",
                    headers=self._auth_header(new_access_token),
                    json=json_body,
                    params=params,
                )
                if resp.status_code == 401:
                    raise CalendarAuthError("Calendar refresh token was rejected — reconnect required.")
                self.credentials["access_token"] = new_access_token
                self.refreshed_access_token = new_access_token

        if resp.status_code >= 400:
            raise IntegrationError(f"Calendar API error {resp.status_code}: {resp.text}")
        return resp.json() if resp.content else {}

    @staticmethod
    def _summarize_event(ev: dict) -> dict:
        start = ev.get("start", {})
        end = ev.get("end", {})
        return {
            "id": ev.get("id"),
            "summary": ev.get("summary"),
            "description": ev.get("description"),
            "location": ev.get("location"),
            "start": start.get("dateTime") or start.get("date"),
            "end": end.get("dateTime") or end.get("date"),
            "all_day": "date" in start and "dateTime" not in start,
            "attendees": [a.get("email") for a in ev.get("attendees", []) if a.get("email")],
            "html_link": ev.get("htmlLink"),
            "status": ev.get("status"),
        }

    # --- Read (direct — no approval) ------------------------------------

    async def list_events(
        self, *, max_results: int = 10, time_min: str | None = None, calendar_id: str = "primary"
    ) -> IntegrationActionResult:
        """Upcoming events by default (time_min omitted -> Calendar API
        still requires a value, so callers pass 'now' in ISO 8601 —
        see calendar_service). singleEvents expands recurring events into
        individual instances so a weekly standup shows once per occurrence,
        not as one unbounded recurring block; orderBy=startTime keeps the
        result in chronological order, matching 'next N events'."""
        params = {
            "maxResults": max_results,
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        if time_min:
            params["timeMin"] = time_min
        data = await self._request("GET", f"/calendars/{calendar_id}/events", params=params)
        events = [self._summarize_event(ev) for ev in data.get("items", [])]
        return IntegrationActionResult(success=True, data=events, message=f"Fetched {len(events)} events.")

    async def get_event(self, event_id: str, *, calendar_id: str = "primary") -> IntegrationActionResult:
        data = await self._request("GET", f"/calendars/{calendar_id}/events/{event_id}")
        return IntegrationActionResult(success=True, data=self._summarize_event(data), message="Fetched event.")

    # --- Approval-gated (called only by capability_executors, post-approval) --

    async def create_event(
        self,
        *,
        summary: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
        attendees: list[str] | None = None,
        all_day: bool = False,
        calendar_id: str = "primary",
    ) -> IntegrationActionResult:
        body: dict = {"summary": summary, "description": description, "location": location}
        if all_day:
            body["start"] = {"date": start}
            body["end"] = {"date": end}
        else:
            body["start"] = {"dateTime": start}
            body["end"] = {"dateTime": end}
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]
        data = await self._request("POST", f"/calendars/{calendar_id}/events", json_body=body)
        return IntegrationActionResult(success=True, data=self._summarize_event(data), message="Event created.")

    async def update_event(
        self,
        *,
        event_id: str,
        summary: str | None = None,
        start: str | None = None,
        end: str | None = None,
        description: str | None = None,
        location: str | None = None,
        all_day: bool = False,
        calendar_id: str = "primary",
    ) -> IntegrationActionResult:
        body: dict = {}
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        if location is not None:
            body["location"] = location
        if start is not None:
            body["start"] = {"date": start} if all_day else {"dateTime": start}
        if end is not None:
            body["end"] = {"date": end} if all_day else {"dateTime": end}
        data = await self._request("PATCH", f"/calendars/{calendar_id}/events/{event_id}", json_body=body)
        return IntegrationActionResult(success=True, data=self._summarize_event(data), message="Event updated.")

    async def delete_event(self, event_id: str, *, calendar_id: str = "primary") -> IntegrationActionResult:
        await self._request("DELETE", f"/calendars/{calendar_id}/events/{event_id}")
        return IntegrationActionResult(success=True, data={"event_id": event_id}, message="Event deleted.")
