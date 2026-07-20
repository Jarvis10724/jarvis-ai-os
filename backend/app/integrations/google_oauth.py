"""
Shared Google OAuth 2.0 REST helpers — the authorization-code flow and
token refresh, usable by any Google-backed capability (Gmail today;
Calendar/Drive later share the same client id/secret and token endpoint,
just a different scope list).

Deliberately plain REST calls via httpx rather than google-api-python-client
— matches the rest of the codebase's integration style (raw HTTP; see
app.integrations.base) and keeps the dependency footprint small. `client`
is always injectable so tests can point it at an httpx.MockTransport
instead of the real network.

GOOGLE_CLIENT_SECRET only ever appears in the body of a server-to-Google
POST request from this module — never in a response returned to the
frontend, never logged.
"""
import httpx

from app.config import settings
from app.exceptions import IntegrationError

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def _require_configured() -> None:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise IntegrationError("Google OAuth is not configured (GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET missing).")


def build_auth_url(*, scopes: list[str], redirect_uri: str, state: str) -> str:
    if not settings.GOOGLE_CLIENT_ID:
        raise IntegrationError("GOOGLE_CLIENT_ID is not configured.")
    scope = "%20".join(scopes)
    return (
        f"{AUTH_URL}?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code&access_type=offline&prompt=consent"
        f"&scope={scope}&state={state}"
    )


async def _post_token_request(payload: dict, *, client: httpx.AsyncClient | None) -> dict:
    owns_client = client is None
    active = client or httpx.AsyncClient(timeout=15.0)
    try:
        resp = await active.post(TOKEN_URL, data=payload)
    finally:
        if owns_client:
            await active.aclose()
    if resp.status_code != 200:
        # Google's standard error for a revoked/expired/invalid refresh
        # token is a 400 with error=invalid_grant — surfaced as-is so
        # callers (health checks, capability actions) can tell "reconnect
        # required" apart from a transient network problem.
        raise IntegrationError(f"Google OAuth request failed: {resp.status_code} {resp.text}")
    return resp.json()


async def exchange_code(*, code: str, redirect_uri: str, client: httpx.AsyncClient | None = None) -> dict:
    """Returns Google's token response: access_token, refresh_token (only
    present on the first consent — Google omits it on subsequent grants
    unless prompt=consent forces a new one, which build_auth_url already
    sets), expires_in, scope, token_type."""
    _require_configured()
    return await _post_token_request(
        {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        client=client,
    )


async def refresh_access_token(*, refresh_token: str, client: httpx.AsyncClient | None = None) -> dict:
    """Returns a fresh access_token (and expires_in); refresh_token is
    normally NOT re-issued here — the caller should keep the existing one
    unless this response happens to include a new one."""
    _require_configured()
    return await _post_token_request(
        {
            "refresh_token": refresh_token,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "grant_type": "refresh_token",
        },
        client=client,
    )
