"""
Google Drive integration — real REST calls against the Drive API v3.

Same shape as app.integrations.email_integration / google_calendar_integration:
list/search and read are the only actions app.core.capabilities_registry's
"google_drive" entry declares today (both direct — no approval needed,
matching capability_service.authorize_direct_action), so there is
deliberately no create/upload/delete here yet — add it the same way Gmail's
send or Calendar's create_event were added (a new ActionDefinition with
requires_approval=True, a propose_* in drive_service, and a dispatch branch
in execute_action) if/when a write action is actually wanted.

Auth: shares the same Google OAuth client (client_id/secret) as Gmail and
Calendar via app.integrations.google_oauth, but requests its own narrower
scope and is stored as its own IntegrationCredential row
(provider="google_drive") — connecting Drive never touches Gmail's or
Calendar's credentials and vice versa. Same in-memory-refresh-on-401
contract as the other two: this class never persists a refreshed
access_token itself (no db session here); app.core.drive_service does that
via `refreshed_access_token`.
"""
import httpx

from app.exceptions import IntegrationError
from app.integrations import google_oauth
from app.integrations.base import BaseIntegration, IntegrationActionResult

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"

# Read-only is the narrowest scope that covers the full action set
# currently registered (list_files, read_document — see
# capabilities_registry's "google_drive" entry). Deliberately NOT
# `drive.file` (which only grants access to files this app itself created
# or the user explicitly opened via a picker — too narrow to "search and
# read" a user's *existing* Drive) and NOT the full `drive` scope (which
# would additionally grant writing/deleting/trashing any file, not needed
# until a write action is actually built).
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Google Workspace "native" doc types have no raw bytes of their own —
# reading their content means asking Drive to export them as plain
# text/CSV first. Anything not in this map is treated as a regular binary/
# text file and downloaded via alt=media instead.
_EXPORT_MIME_MAP = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}


class DriveAuthError(IntegrationError):
    """A Drive API call failed with 401 even after a refresh attempt — the
    refresh_token itself is invalid/revoked. Distinct from a generic
    IntegrationError so callers (health checks, capability actions) can
    tell the user 'reconnect Drive' instead of a generic failure message."""

    code = "drive_auth_error"


class GoogleDriveIntegration(BaseIntegration):
    name = "google_drive"
    description = "Google Drive / Docs — search and read documents."

    def __init__(self, credentials: dict | None = None):
        super().__init__(credentials)
        # Set by _authed_request() when a 401 forced an in-memory refresh —
        # the caller (app.core.drive_service) checks this after every call
        # and persists it via credential_store if present. Never read by
        # anything inside this class.
        self.refreshed_access_token: str | None = None

    @staticmethod
    def _auth_header(access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    async def is_connected(self) -> bool:
        """Real connectivity probe (GET .../about), not just 'is there a
        token string'. Attempts an in-memory refresh if the current
        access_token is stale so a merely-expired-but-refreshable token
        still reports connected; a revoked/invalid refresh_token reports
        disconnected. Never persists a refreshed token (no db session
        here) — the next real action call does that via drive_service."""
        access_token = self.credentials.get("access_token")
        if not access_token:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{DRIVE_API_BASE}/about", params={"fields": "user"}, headers=self._auth_header(access_token)
            )
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
                f"{DRIVE_API_BASE}/about", params={"fields": "user"}, headers=self._auth_header(token_data["access_token"])
            )
            return retry.status_code == 200

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        return google_oauth.build_auth_url(scopes=DRIVE_SCOPES, redirect_uri=redirect_uri, state=state)

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        return await google_oauth.exchange_code(code=code, redirect_uri=redirect_uri)

    async def _authed_request(
        self, method: str, path: str, *, params: dict | None = None, expect_json: bool = True
    ) -> httpx.Response:
        """Every real Drive API call funnels through here so the
        401-refresh-and-retry logic lives in exactly one place. Returns the
        raw httpx.Response so callers needing JSON (list/get metadata) and
        callers needing raw bytes/text (export, alt=media download) can
        each read it the way they need — Drive's export/download endpoints
        don't return JSON at all."""
        access_token = self.credentials.get("access_token")
        if not access_token:
            raise DriveAuthError("Drive is not connected (no access token).")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, f"{DRIVE_API_BASE}{path}", headers=self._auth_header(access_token), params=params)
            if resp.status_code == 401:
                refresh_token = self.credentials.get("refresh_token")
                if not refresh_token:
                    raise DriveAuthError(
                        "Drive access token expired and no refresh token is stored — reconnect required."
                    )
                token_data = await google_oauth.refresh_access_token(refresh_token=refresh_token, client=client)
                new_access_token = token_data["access_token"]
                resp = await client.request(
                    method, f"{DRIVE_API_BASE}{path}", headers=self._auth_header(new_access_token), params=params
                )
                if resp.status_code == 401:
                    raise DriveAuthError("Drive refresh token was rejected — reconnect required.")
                self.credentials["access_token"] = new_access_token
                self.refreshed_access_token = new_access_token

        if resp.status_code >= 400:
            raise IntegrationError(f"Drive API error {resp.status_code}: {resp.text}")
        return resp

    # --- Read (direct — no approval) ------------------------------------

    async def list_files(self, *, query: str = "", max_results: int = 10) -> IntegrationActionResult:
        """Powers both 'list my files' (query="") and 'search Drive'
        (query="report", "name contains 'invoice'", etc. — Drive's search
        syntax passed straight through via the `q` param)."""
        params = {
            "pageSize": max_results,
            "fields": "files(id,name,mimeType,modifiedTime,webViewLink,owners(displayName,emailAddress))",
            "orderBy": "modifiedTime desc",
        }
        if query:
            # Bare search terms are the common case ("find the Q3 deck") —
            # translate to Drive's `name contains` syntax unless the caller
            # already passed real Drive query syntax (contains an operator).
            params["q"] = query if any(op in query for op in ("=", "contains", "in ")) else f"name contains '{query}'"
        resp = await self._authed_request("GET", "/files", params=params)
        data = resp.json()
        files = [
            {
                "id": f["id"],
                "name": f.get("name"),
                "mime_type": f.get("mimeType"),
                "modified_time": f.get("modifiedTime"),
                "web_view_link": f.get("webViewLink"),
                "owners": [o.get("emailAddress") for o in f.get("owners", [])],
                "is_google_doc": f.get("mimeType") in _EXPORT_MIME_MAP,
            }
            for f in data.get("files", [])
        ]
        return IntegrationActionResult(success=True, data=files, message=f"Fetched {len(files)} files.")

    async def find_folder_id(self, name: str) -> str | None:
        """Resolves a folder's Drive file id by exact name match — how a
        company workspace's file listing gets scoped to its own folder
        (see app.core.drive_service) without storing a separate mapping
        anywhere: the convention is simply 'a folder named exactly like
        the company'. Returns None if no such folder exists — a missing
        folder isn't a connection error, callers fall back to an unscoped
        listing instead."""
        escaped = name.replace("'", "\\'")
        resp = await self._authed_request(
            "GET",
            "/files",
            params={
                "q": f"name = '{escaped}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                "fields": "files(id,name)",
                "pageSize": 1,
            },
        )
        files = resp.json().get("files", [])
        return files[0]["id"] if files else None

    async def read_document(self, file_id: str) -> IntegrationActionResult:
        """Reads a file's text content. Google Docs/Sheets/Slides have no
        raw bytes of their own, so those are exported as plain text/CSV
        first; anything else is downloaded via alt=media and decoded as
        UTF-8 best-effort (binary formats like images/PDFs report back
        that they aren't text-extractable rather than returning garbage)."""
        meta_resp = await self._authed_request("GET", f"/files/{file_id}", params={"fields": "id,name,mimeType"})
        meta = meta_resp.json()
        mime_type = meta.get("mimeType", "")
        name = meta.get("name")

        if mime_type in _EXPORT_MIME_MAP:
            content_resp = await self._authed_request(
                "GET", f"/files/{file_id}/export", params={"mimeType": _EXPORT_MIME_MAP[mime_type]}
            )
            content = content_resp.text
            extractable = True
        elif mime_type.startswith("text/") or mime_type in ("application/json",):
            content_resp = await self._authed_request("GET", f"/files/{file_id}", params={"alt": "media"})
            content = content_resp.text
            extractable = True
        else:
            content = ""
            extractable = False

        return IntegrationActionResult(
            success=True,
            data={
                "id": file_id,
                "name": name,
                "mime_type": mime_type,
                "content": content,
                "extractable": extractable,
                "message": None if extractable else f"'{name}' is a {mime_type} file — not text-extractable.",
            },
            message="Fetched document." if extractable else "File is not text-extractable.",
        )
