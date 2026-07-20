"""
Coverage for the Gmail capability: the server-side OAuth flow (state
validation, token exchange, refresh), company-scoped credentials, the
direct-vs-approval action split, and graceful handling of a revoked
refresh token.

No real network access — every httpx.AsyncClient.request call made by
app.integrations.google_oauth / app.integrations.email_integration is
intercepted by a small fake-router (see _patch_httpx below) and answered
with canned Gmail/Google-OAuth-shaped responses. FastAPI's own TestClient
is unaffected — it's built on a *sync* httpx.Client with an ASGI
transport, a different class from the httpx.AsyncClient this module
patches, so there's no interference between "calling our API" and
"our API calling Google."
"""
import base64
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.config import settings
from app.core import credential_store
from app.db.models.oauth_state import OAuthState
from app.db.session import SessionLocal

API = "/api/v1"


@pytest.fixture(autouse=True)
def _configure_google_oauth(monkeypatch):
    # Deterministic regardless of whatever the real machine's .env has (or
    # doesn't have) set for these — every test in this file needs Google
    # OAuth to look "configured" without touching real credentials.
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "http://testserver/api/v1/integrations/email/callback")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_REDIRECT_BASE_URL", "http://testserver/api/v1/integrations")


# ---------------------------------------------------------------------------
# Fake Google/Gmail HTTP layer
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, json_data: dict | None = None, text: str | None = None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text if text is not None else str(self._json)
        self.content = b"{}" if json_data is not None else b""

    def json(self):
        return self._json


def _sequence(*responses: _FakeResponse):
    """A rule handler that returns each response in order on successive
    matching calls, then repeats the last one for any further calls."""
    responses = list(responses)
    calls = {"n": 0}

    def handler(method, url, **kwargs):
        idx = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[idx]

    return handler


def _patch_httpx(monkeypatch, rules: list[tuple]):
    """rules: list of (predicate(method, url) -> bool, handler). `handler`
    is either a plain _FakeResponse (returned as-is — the common case) or a
    callable(method, url, **kwargs) -> _FakeResponse for anything that
    needs to vary across calls (_sequence) or inspect the request
    (_capture_send). First matching predicate wins. Patches the exact
    method every real Gmail/OAuth call in this codebase goes through
    (AsyncClient.request — .get()/.post() are thin wrappers around it)."""

    async def fake_request(self, method, url, **kwargs):
        url_str = str(url)
        for predicate, handler in rules:
            if predicate(method, url_str):
                return handler(method, url_str, **kwargs) if callable(handler) else handler
        raise AssertionError(f"Unexpected HTTP request in test: {method} {url_str}")

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)


def _is_token_url(method, url):
    return method == "POST" and "oauth2.googleapis.com/token" in url


def _is_profile_url(method, url):
    return method == "GET" and url.rstrip("/").endswith("/profile")


def _is_bare_messages_url(method, url):
    return method == "GET" and url.split("?")[0].rstrip("/").endswith("/messages")


def _is_message_detail_url(method, url, message_id="m1"):
    path = url.split("?")[0]
    return method == "GET" and path.rstrip("/").endswith(f"/messages/{message_id}")


def _token_ok(access_token="AT1", refresh_token=None, extra: dict | None = None):
    data = {"access_token": access_token, "expires_in": 3600, "token_type": "Bearer", "scope": "gmail.readonly gmail.modify"}
    if refresh_token:
        data["refresh_token"] = refresh_token
    if extra:
        data.update(extra)
    return _FakeResponse(200, data)


def _token_revoked():
    return _FakeResponse(400, {"error": "invalid_grant", "error_description": "Token has been expired or revoked."})


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def _list_ok(ids: list[str]):
    return _FakeResponse(200, {"messages": [{"id": i} for i in ids]})


def _detail_ok(message_id: str, *, subject="Hello", frm="sender@example.com", body="Body text here.", unread=False):
    return _FakeResponse(
        200,
        {
            "id": message_id,
            "threadId": f"thread-{message_id}",
            "snippet": body[:50],
            "labelIds": (["UNREAD"] if unread else []) + ["INBOX"],
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": frm},
                    {"name": "Subject", "value": subject},
                    {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                    {"name": "Message-ID", "value": f"<{message_id}@mail.example.com>"},
                ],
                "body": {"data": _b64(body)},
            },
        },
    )


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, email: str, password: str = "supersecret123") -> dict:
    client.post(f"{API}/auth/register", json={"email": email, "password": password})
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_company(client, headers: dict, name: str) -> str:
    resp = client.post(f"{API}/companies", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _connect_gmail(client, monkeypatch, headers: dict, company_id: str | None, *, access_token="AT1", refresh_token="RT1") -> str:
    """Runs the full authorize-url -> callback flow with a mocked token
    exchange, returns the `state` value used (handy for replay tests)."""
    _patch_httpx(monkeypatch, [(_is_token_url, _token_ok(access_token, refresh_token))])

    qs = f"?company_id={company_id}" if company_id else ""
    auth_resp = client.get(f"{API}/integrations/email/authorize-url{qs}", headers=headers)
    assert auth_resp.status_code == 200, auth_resp.text
    url = auth_resp.json()["url"]
    assert "accounts.google.com" in url
    assert "gmail.readonly" in url and "gmail.modify" in url

    state = url.split("state=")[1].split("&")[0]
    callback_resp = client.get(
        f"{API}/integrations/email/callback",
        params={"code": "fake-auth-code", "state": state},
        follow_redirects=False,
    )
    assert callback_resp.status_code in (302, 307), callback_resp.text
    assert "connected=email" in callback_resp.headers["location"]
    return state


# ---------------------------------------------------------------------------
# OAuth state validation
# ---------------------------------------------------------------------------


def test_authorize_url_contains_state_and_narrow_scopes(client):
    headers = _register_and_login(client, "gmail-authurl@example.com")
    resp = client.get(f"{API}/integrations/email/authorize-url", headers=headers)
    assert resp.status_code == 200, resp.text
    url = resp.json()["url"]
    assert "state=" in url
    assert "client_id=test-client-id" in url
    # Narrowest-sufficient scope set — no gmail.compose (redundant with
    # gmail.modify) and definitely not the full mail.google.com scope.
    assert "gmail.readonly" in url
    assert "gmail.modify" in url
    assert "mail.google.com" not in url


def test_callback_with_unknown_state_is_rejected(client):
    resp = client.get(
        f"{API}/integrations/email/callback", params={"code": "x", "state": "totally-made-up-state"}
    )
    assert resp.status_code == 401


def test_callback_state_is_single_use(client, monkeypatch):
    headers = _register_and_login(client, "gmail-state-replay@example.com")
    state = _connect_gmail(client, monkeypatch, headers, company_id=None)

    replay = client.get(f"{API}/integrations/email/callback", params={"code": "another-code", "state": state})
    assert replay.status_code == 401


def test_callback_rejects_expired_state(client):
    headers = _register_and_login(client, "gmail-state-expired@example.com")
    user_id = client.get(f"{API}/auth/me", headers=headers).json()["id"]

    db = SessionLocal()
    try:
        expired = OAuthState(
            state="expired-state-token",
            user_id=user_id,
            company_id=None,
            capability_name="email",
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.add(expired)
        db.commit()
    finally:
        db.close()

    resp = client.get(f"{API}/integrations/email/callback", params={"code": "x", "state": "expired-state-token"})
    assert resp.status_code == 401


def test_callback_rejects_state_issued_for_a_different_capability(client):
    headers = _register_and_login(client, "gmail-state-wrong-capability@example.com")
    resp = client.get(f"{API}/integrations/email/authorize-url", headers=headers)
    state = resp.json()["url"].split("state=")[1].split("&")[0]

    # This state was issued for "email" — using it against a different
    # capability's callback must fail even though "google_drive" is itself
    # a valid, registered capability name.
    wrong_capability = client.get(
        f"{API}/integrations/google_drive/callback", params={"code": "x", "state": state}
    )
    assert wrong_capability.status_code == 401


# ---------------------------------------------------------------------------
# Company isolation
# ---------------------------------------------------------------------------


def test_gmail_credentials_isolated_per_company(client, monkeypatch):
    headers = _register_and_login(client, "gmail-company-isolation@example.com")
    company_a = _create_company(client, headers, "GmailCoA")
    company_b = _create_company(client, headers, "GmailCoB")

    _connect_gmail(client, monkeypatch, headers, company_id=company_a, access_token="AT_A", refresh_token="RT_A")

    _patch_httpx(
        monkeypatch,
        [(_is_bare_messages_url, _list_ok(["m1"])), (_is_message_detail_url, _detail_ok("m1"))],
    )
    ok_resp = client.get(f"{API}/gmail/messages", params={"company_id": company_a}, headers=headers)
    assert ok_resp.status_code == 200, ok_resp.text
    assert len(ok_resp.json()) == 1

    not_connected_resp = client.get(f"{API}/gmail/messages", params={"company_id": company_b}, headers=headers)
    assert not_connected_resp.status_code == 422


def test_disconnect_only_affects_that_company(client, monkeypatch):
    headers = _register_and_login(client, "gmail-disconnect-isolation@example.com")
    company_a = _create_company(client, headers, "DisconnectCoA")
    company_b = _create_company(client, headers, "DisconnectCoB")
    _connect_gmail(client, monkeypatch, headers, company_id=company_a)
    _connect_gmail(client, monkeypatch, headers, company_id=company_b)

    del_resp = client.delete(f"{API}/integrations/email", params={"company_id": company_a}, headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    _patch_httpx(monkeypatch, [(_is_bare_messages_url, _list_ok([])), (_is_message_detail_url, _detail_ok("m1"))])
    a_resp = client.get(f"{API}/gmail/messages", params={"company_id": company_a}, headers=headers)
    assert a_resp.status_code == 422  # gone

    b_resp = client.get(f"{API}/gmail/messages", params={"company_id": company_b}, headers=headers)
    assert b_resp.status_code == 200  # untouched


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


def test_expired_access_token_is_refreshed_and_persisted(client, monkeypatch):
    headers = _register_and_login(client, "gmail-token-refresh@example.com")
    _connect_gmail(client, monkeypatch, headers, company_id=None, access_token="AT_OLD", refresh_token="RT_KEEP")

    # First call to the bare /messages list 401s (stale access token); the
    # in-code refresh-and-retry kicks in, refresh returns a new access
    # token (deliberately WITHOUT a refresh_token, matching real Google
    # behavior), and the retried call succeeds.
    _patch_httpx(
        monkeypatch,
        [
            (_is_token_url, _token_ok("AT_NEW")),
            (_is_bare_messages_url, _sequence(_FakeResponse(401), _list_ok(["m1"]))),
            (_is_message_detail_url, _detail_ok("m1")),
        ],
    )
    resp = client.get(f"{API}/gmail/messages", headers=headers)
    assert resp.status_code == 200, resp.text

    # Verify persistence directly against the encrypted store: the new
    # access token was written, and the ORIGINAL refresh token was kept —
    # a refresh response omitting refresh_token must never null it out.
    user_id = client.get(f"{API}/auth/me", headers=headers).json()["id"]
    db = SessionLocal()
    try:
        stored = credential_store.load_credentials(db, owner_id=user_id, company_id=None, provider="email")
    finally:
        db.close()
    assert stored["access_token"] == "AT_NEW"
    assert stored["refresh_token"] == "RT_KEEP"


def test_access_token_encrypted_at_rest(client, monkeypatch):
    headers = _register_and_login(client, "gmail-encrypted-at-rest@example.com")
    _connect_gmail(client, monkeypatch, headers, company_id=None, access_token="PLAINTEXT_TOKEN_VALUE", refresh_token="RT1")

    user_id = client.get(f"{API}/auth/me", headers=headers).json()["id"]
    db = SessionLocal()
    try:
        from app.db.models.integration_credential import IntegrationCredential

        row = (
            db.query(IntegrationCredential)
            .filter(IntegrationCredential.owner_id == user_id, IntegrationCredential.provider == "email")
            .first()
        )
        assert row is not None
        # Raw column value must never equal (or contain) the plaintext.
        assert row.access_token != "PLAINTEXT_TOKEN_VALUE"
        assert "PLAINTEXT_TOKEN_VALUE" not in (row.access_token or "")

        decrypted = credential_store.load_credentials(db, owner_id=user_id, company_id=None, provider="email")
        assert decrypted["access_token"] == "PLAINTEXT_TOKEN_VALUE"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Revoked credentials
# ---------------------------------------------------------------------------


def test_revoked_refresh_token_fails_cleanly_not_crash(client, monkeypatch):
    headers = _register_and_login(client, "gmail-revoked@example.com")
    _connect_gmail(client, monkeypatch, headers, company_id=None, access_token="AT_STALE", refresh_token="RT_REVOKED")

    _patch_httpx(
        monkeypatch,
        [
            (_is_bare_messages_url, _FakeResponse(401)),
            (_is_token_url, _token_revoked()),
        ],
    )
    resp = client.get(f"{API}/gmail/messages", headers=headers)
    # A clean, typed failure (IntegrationError/GmailAuthError -> 502), not
    # an unhandled 500 — the request never gets stuck retrying forever.
    assert resp.status_code == 502
    assert "error" in resp.json()


def test_health_check_reports_disconnected_when_refresh_token_revoked(client, monkeypatch):
    headers = _register_and_login(client, "gmail-revoked-health@example.com")
    _connect_gmail(client, monkeypatch, headers, company_id=None, access_token="AT_STALE", refresh_token="RT_REVOKED")

    _patch_httpx(
        monkeypatch,
        [
            (_is_profile_url, _FakeResponse(401)),
            (_is_token_url, _token_revoked()),
        ],
    )
    resp = client.post(f"{API}/capabilities/email/health-check", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["health_status"] == "disconnected"


# ---------------------------------------------------------------------------
# Approval enforcement — direct (read/draft) vs. gated (send/forward/...)
# ---------------------------------------------------------------------------


def test_list_search_and_draft_execute_directly_without_any_approval(client, monkeypatch):
    headers = _register_and_login(client, "gmail-direct-actions@example.com")
    _connect_gmail(client, monkeypatch, headers, company_id=None)

    _patch_httpx(
        monkeypatch,
        [
            (_is_bare_messages_url, _list_ok(["m1"])),
            (_is_message_detail_url, _detail_ok("m1", subject="Invoice due", unread=True)),
            (lambda m, u: m == "POST" and u.rstrip("/").endswith("/drafts"), lambda m, u, **kw: _FakeResponse(200, {"id": "draft-1"})),
        ],
    )

    listed = client.get(f"{API}/gmail/messages", params={"unread_only": True}, headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["subject"] == "Invoice due"

    drafted = client.post(f"{API}/gmail/drafts", json={"to": "x@y.com", "subject": "Hi", "body": "..."}, headers=headers)
    assert drafted.status_code == 201
    assert drafted.json()["draft_id"] == "draft-1"

    # Neither of the above should have created anything in the approval queue.
    approvals = client.get(f"{API}/approvals", params={"company_id": "any"}, headers=headers).json()
    assert approvals == []


def test_send_is_blocked_until_permitted_then_requires_approval_to_execute(client, monkeypatch):
    headers = _register_and_login(client, "gmail-send-approval@example.com")
    _connect_gmail(client, monkeypatch, headers, company_id=None)

    # Not permitted yet — send is approval-gated AND opt-in, per capability
    # framework rules (write actions are never on by default).
    blocked = client.post(
        f"{API}/gmail/send", json={"to": "x@y.com", "subject": "Hi", "body": "..."}, headers=headers
    )
    assert blocked.status_code == 403

    grant = client.put(
        f"{API}/capabilities/email/config",
        json={"enabled": True, "permissions": ["list_messages", "draft", "send"], "company_id": None},
        headers=headers,
    )
    assert grant.status_code == 200

    proposed = client.post(
        f"{API}/gmail/send", json={"to": "x@y.com", "subject": "Hi", "body": "..."}, headers=headers
    )
    assert proposed.status_code == 201, proposed.text
    request_id = proposed.json()["id"]
    assert proposed.json()["status"] == "pending"

    sent_calls = []

    def _capture_send(method, url, **kwargs):
        sent_calls.append(kwargs.get("json"))
        return _FakeResponse(200, {"id": "sent-message-1"})

    _patch_httpx(monkeypatch, [(lambda m, u: m == "POST" and u.rstrip("/").endswith("/messages/send"), _capture_send)])

    approved = client.post(f"{API}/approvals/{request_id}/approve", json={}, headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "executed"
    assert len(sent_calls) == 1
    assert sent_calls[0] is not None  # the raw MIME payload was actually sent


def test_forward_trash_archive_labels_all_require_approval(client, monkeypatch):
    headers = _register_and_login(client, "gmail-gated-actions@example.com")
    _connect_gmail(client, monkeypatch, headers, company_id=None)
    client.put(
        f"{API}/capabilities/email/config",
        json={"enabled": True, "permissions": ["forward", "trash", "archive", "modify_labels"], "company_id": None},
        headers=headers,
    )

    forward_resp = client.post(
        f"{API}/gmail/messages/m1/forward", json={"to": "z@y.com", "note": "fyi"}, headers=headers
    )
    assert forward_resp.status_code == 201
    assert forward_resp.json()["status"] == "pending"

    trash_resp = client.post(f"{API}/gmail/messages/m1/trash", json={}, headers=headers)
    assert trash_resp.status_code == 201
    assert trash_resp.json()["status"] == "pending"

    archive_resp = client.post(f"{API}/gmail/messages/m1/archive", json={}, headers=headers)
    assert archive_resp.status_code == 201
    assert archive_resp.json()["status"] == "pending"

    labels_resp = client.post(
        f"{API}/gmail/messages/m1/labels", json={"add_labels": ["IMPORTANT"]}, headers=headers
    )
    assert labels_resp.status_code == 201
    assert labels_resp.json()["status"] == "pending"

    # None of these executed anything yet — no Gmail write call was made,
    # so no httpx patch was even needed for the propose step itself.
    for resp in (forward_resp, trash_resp, archive_resp, labels_resp):
        assert resp.json()["action_type"] in {"forward", "trash", "archive", "modify_labels"}
