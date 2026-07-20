"""
Gmail integration — real REST calls against the Gmail API v1.

Read (inbox listing, search, single-message fetch) and draft creation
execute directly, no approval needed. Send, trash/delete, archive, forward,
and label changes are only ever invoked by the executor that runs AFTER an
ApprovalRequest is approved (see app.core.capability_executors) — this
class has no opinion about approval; it just does what it's told. See
app.core.capabilities_registry's "email" entry for the authoritative list
of which action is gated.

Auth: this class only ever sees an access_token/refresh_token pair handed
to it via `credentials` (already decrypted by app.core.credential_store).
It refreshes an expired access_token in-memory when a call 401s, but it
never persists the refreshed token itself — BaseIntegration instances don't
hold a database session, so app.core.gmail_service (which does) is
responsible for calling credential_store.save_credentials() when
`refreshed_access_token` comes back non-None after a call.
"""
import base64
from email.mime.text import MIMEText

import httpx

from app.exceptions import IntegrationError
from app.integrations import google_oauth
from app.integrations.base import BaseIntegration, IntegrationActionResult

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

# Narrowest scopes that still cover the full action set requested:
#   - gmail.readonly: list/search/get messages.
#   - gmail.modify: create/send drafts, send messages, trash, archive
#     (label removal), and label changes — a superset of gmail.compose, so
#     gmail.compose is deliberately NOT also requested (would be
#     redundant). Explicitly NOT the full `mail.google.com` scope, which
#     additionally grants permanent delete and account settings changes
#     this capability never needs.
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


class GmailAuthError(IntegrationError):
    """A Gmail API call failed with 401 even after a refresh attempt — the
    refresh_token itself is invalid/revoked. Distinct from a generic
    IntegrationError so callers (health checks, capability actions) can
    tell the user 'reconnect Gmail' instead of a generic failure message."""

    code = "gmail_auth_error"


class EmailIntegration(BaseIntegration):
    name = "email"
    description = "Gmail — read, search, summarize, draft, and send."

    def __init__(self, credentials: dict | None = None):
        super().__init__(credentials)
        # Set by _request() when a 401 forced an in-memory refresh — the
        # caller (app.core.gmail_service) checks this after every call and
        # persists it via credential_store if present. Never read by
        # anything inside this class.
        self.refreshed_access_token: str | None = None

    @staticmethod
    def _auth_header(access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    async def is_connected(self) -> bool:
        """A real connectivity probe (GET .../profile), not just 'is there
        a token string'. Attempts an in-memory refresh if the current
        access_token is stale so a merely-expired-but-refreshable token
        still reports connected; a revoked/invalid refresh_token reports
        disconnected. Never persists a refreshed token (no db session
        here) — the next real action call does that via gmail_service."""
        access_token = self.credentials.get("access_token")
        if not access_token:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{GMAIL_API_BASE}/profile", headers=self._auth_header(access_token))
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
                f"{GMAIL_API_BASE}/profile", headers=self._auth_header(token_data["access_token"])
            )
            return retry.status_code == 200

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        return google_oauth.build_auth_url(scopes=GMAIL_SCOPES, redirect_uri=redirect_uri, state=state)

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        return await google_oauth.exchange_code(code=code, redirect_uri=redirect_uri)

    async def _request(
        self, method: str, path: str, *, json_body: dict | None = None, params: dict | None = None
    ) -> dict:
        """Every real Gmail API call funnels through here so the
        401-refresh-and-retry logic lives in exactly one place."""
        access_token = self.credentials.get("access_token")
        if not access_token:
            raise GmailAuthError("Gmail is not connected (no access token).")

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.request(
                method,
                f"{GMAIL_API_BASE}{path}",
                headers=self._auth_header(access_token),
                json=json_body,
                params=params,
            )
            if resp.status_code == 401:
                refresh_token = self.credentials.get("refresh_token")
                if not refresh_token:
                    raise GmailAuthError(
                        "Gmail access token expired and no refresh token is stored — reconnect required."
                    )
                token_data = await google_oauth.refresh_access_token(refresh_token=refresh_token, client=client)
                new_access_token = token_data["access_token"]
                resp = await client.request(
                    method,
                    f"{GMAIL_API_BASE}{path}",
                    headers=self._auth_header(new_access_token),
                    json=json_body,
                    params=params,
                )
                if resp.status_code == 401:
                    raise GmailAuthError("Gmail refresh token was rejected — reconnect required.")
                self.credentials["access_token"] = new_access_token
                self.refreshed_access_token = new_access_token

        if resp.status_code >= 400:
            raise IntegrationError(f"Gmail API error {resp.status_code}: {resp.text}")
        return resp.json() if resp.content else {}

    # --- Read (direct — no approval) ------------------------------------

    async def list_messages(self, *, max_results: int = 10, query: str = "") -> IntegrationActionResult:
        """Powers both 'read inbox' (query="") and 'search emails'
        (query="from:someone", "is:unread", etc. — Gmail's search syntax
        passed straight through)."""
        params: dict = {"maxResults": max_results}
        if query:
            params["q"] = query
        data = await self._request("GET", "/messages", params=params)
        messages = []
        for ref in data.get("messages", []):
            detail = await self._request(
                "GET",
                f"/messages/{ref['id']}",
                params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
            )
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            label_ids = detail.get("labelIds", [])
            messages.append(
                {
                    "id": detail["id"],
                    "thread_id": detail.get("threadId"),
                    "snippet": detail.get("snippet"),
                    "from": headers.get("From"),
                    "subject": headers.get("Subject"),
                    "date": headers.get("Date"),
                    "unread": "UNREAD" in label_ids,
                    "important": "IMPORTANT" in label_ids,
                    "label_ids": label_ids,
                }
            )
        return IntegrationActionResult(success=True, data=messages, message=f"Fetched {len(messages)} messages.")

    async def list_unread(self, *, max_results: int = 10) -> IntegrationActionResult:
        return await self.list_messages(max_results=max_results, query="is:unread")

    async def get_message(self, message_id: str) -> IntegrationActionResult:
        detail = await self._request("GET", f"/messages/{message_id}", params={"format": "full"})
        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        body = self._extract_body(detail.get("payload", {}))
        return IntegrationActionResult(
            success=True,
            data={
                "id": detail["id"],
                "thread_id": detail.get("threadId"),
                "snippet": detail.get("snippet"),
                "from": headers.get("From"),
                "to": headers.get("To"),
                "subject": headers.get("Subject"),
                "date": headers.get("Date"),
                "message_id_header": headers.get("Message-ID") or headers.get("Message-Id"),
                "body": body,
                "label_ids": detail.get("labelIds", []),
            },
            message="Fetched message.",
        )

    @staticmethod
    def _extract_body(payload: dict) -> str:
        def _decode(data: str) -> str:
            return base64.urlsafe_b64decode(data.encode() + b"==").decode("utf-8", errors="replace")

        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            return _decode(payload["body"]["data"])
        for part in payload.get("parts", []) or []:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return _decode(part["body"]["data"])
        for part in payload.get("parts", []) or []:
            nested = EmailIntegration._extract_body(part)
            if nested:
                return nested
        return payload.get("snippet", "") or ""

    # --- Draft (direct — no approval) ------------------------------------

    @staticmethod
    def _build_raw_message(
        *, to: str, subject: str, body: str, in_reply_to: str | None = None
    ) -> str:
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        if in_reply_to:
            # Proper reply threading — matches the original message's
            # RFC822 Message-ID so Gmail (and the recipient's client)
            # groups this as a reply rather than a new thread.
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to
        return base64.urlsafe_b64encode(msg.as_bytes()).decode()

    async def create_draft(
        self, *, to: str, subject: str, body: str, thread_id: str | None = None, in_reply_to: str | None = None
    ) -> IntegrationActionResult:
        raw = self._build_raw_message(to=to, subject=subject, body=body, in_reply_to=in_reply_to)
        message_payload: dict = {"raw": raw}
        if thread_id:
            message_payload["threadId"] = thread_id
        data = await self._request("POST", "/drafts", json_body={"message": message_payload})
        return IntegrationActionResult(success=True, data={"draft_id": data.get("id")}, message="Draft created.")

    async def draft_reply(self, *, message_id: str, body: str) -> IntegrationActionResult:
        """Convenience wrapper for 'draft a reply to message X' — pulls the
        original's subject/thread/Message-ID so the reply threads
        correctly, then delegates to create_draft."""
        original = (await self.get_message(message_id)).data
        subject = original.get("subject") or ""
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        return await self.create_draft(
            to=original.get("from", ""),
            subject=subject,
            body=body,
            thread_id=original.get("thread_id"),
            in_reply_to=original.get("message_id_header"),
        )

    # --- Approval-gated (called only by capability_executors, post-approval) --

    async def send_message(
        self, *, to: str, subject: str, body: str, thread_id: str | None = None, in_reply_to: str | None = None
    ) -> IntegrationActionResult:
        raw = self._build_raw_message(to=to, subject=subject, body=body, in_reply_to=in_reply_to)
        payload: dict = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id
        data = await self._request("POST", "/messages/send", json_body=payload)
        return IntegrationActionResult(success=True, data={"message_id": data.get("id")}, message="Email sent.")

    async def forward_message(self, *, message_id: str, to: str, note: str = "") -> IntegrationActionResult:
        original = (await self.get_message(message_id)).data
        subject = original.get("subject") or ""
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}"
        body = f"{note}\n\n---------- Forwarded message ----------\n{original.get('body', '')}"
        return await self.send_message(to=to, subject=subject, body=body)

    async def trash_message(self, *, message_id: str) -> IntegrationActionResult:
        await self._request("POST", f"/messages/{message_id}/trash")
        return IntegrationActionResult(success=True, data={"message_id": message_id}, message="Message moved to trash.")

    async def archive_message(self, *, message_id: str) -> IntegrationActionResult:
        data = await self._request("POST", f"/messages/{message_id}/modify", json_body={"removeLabelIds": ["INBOX"]})
        return IntegrationActionResult(
            success=True, data={"message_id": message_id, "label_ids": data.get("labelIds", [])}, message="Message archived."
        )

    async def modify_labels(
        self, *, message_id: str, add_labels: list[str] | None = None, remove_labels: list[str] | None = None
    ) -> IntegrationActionResult:
        payload: dict = {}
        if add_labels:
            payload["addLabelIds"] = add_labels
        if remove_labels:
            payload["removeLabelIds"] = remove_labels
        data = await self._request("POST", f"/messages/{message_id}/modify", json_body=payload)
        return IntegrationActionResult(
            success=True, data={"message_id": message_id, "label_ids": data.get("labelIds", [])}, message="Labels updated."
        )
