"""
The OAuth plumbing every integration shares: connection status, the
authorize-url the frontend redirects the browser to, the callback Google
(or any future OAuth provider) redirects back to, and disconnect.

Server-side authorization-code flow, by design: the frontend never sees
GOOGLE_CLIENT_SECRET, never sees an access/refresh token, and never talks
to Google directly — it only ever calls these two Jarvis endpoints
(authorize-url, then a plain browser redirect) and later reads connection
status. See app.core.credential_store for encryption-at-rest and
app.core.oauth_state_service for the CSRF-safe state handling that makes
the callback endpoint safe to leave unauthenticated (it has to be — the
browser's top-level redirect back from Google carries no Bearer token).
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.config import settings
from app.core import credential_store, oauth_state_service
from app.core.capabilities_registry import get_capability
from app.db.models.company import Company
from app.db.session import get_db
from app.exceptions import IntegrationError, NotFoundError
from app.integrations.registry import get_integration, list_integrations

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _assert_company_owned(db: Session, company_id: str, owner_id: str) -> None:
    exists = db.query(Company.id).filter(Company.id == company_id, Company.owner_id == owner_id).first()
    if not exists:
        raise NotFoundError(f"Company '{company_id}' not found (or it isn't yours).")


def _redirect_uri_for(name: str) -> str:
    """Every Google-backed capability gets its own callback URL
    (.../integrations/{name}/callback), derived from one configured base
    rather than a single fixed GOOGLE_REDIRECT_URI shared by every
    capability. Sharing one fixed URL was the original bug: Google always
    redirects back to whatever exact URL was sent in the authorize
    request, so if every capability requested the *same* redirect_uri, the
    callback could never tell which capability a given state belonged to
    from the URL alone — and the state row's own capability_name would
    then mismatch the path's hardcoded name, failing with 'Invalid or
    expired OAuth state' (see oauth_state_service.consume_state). Each
    capability having its own distinct, exact-match URL fixes that at the
    source instead of trying to detect it after the fact."""
    if not settings.GOOGLE_OAUTH_REDIRECT_BASE_URL:
        raise IntegrationError("GOOGLE_OAUTH_REDIRECT_BASE_URL is not configured.")
    return f"{settings.GOOGLE_OAUTH_REDIRECT_BASE_URL}/{name}/callback"


class IntegrationStatus(BaseModel):
    name: str
    description: str
    connected: bool


@router.get("", response_model=list[IntegrationStatus])
async def list_all(
    current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None)
):
    statuses = []
    for info in list_integrations():
        creds = credential_store.load_credentials(
            db, owner_id=current_user.id, company_id=company_id, provider=info["name"]
        )
        integration = get_integration(info["name"], credentials=creds or {})
        statuses.append(
            IntegrationStatus(name=info["name"], description=info["description"], connected=await integration.is_connected())
        )
    return statuses


@router.get("/{name}/authorize-url")
def get_authorize_url(
    name: str, current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None)
):
    """Returns the Google consent URL to send the browser to. The redirect
    target is always our own fixed, capability-specific backend callback
    (see _redirect_uri_for — must exactly match one of the "Authorized
    redirect URIs" registered in Google Cloud Console for this OAuth
    client) — never a caller-supplied URL, so this can't be turned into an
    open redirect."""
    capability_def = get_capability(name)
    if company_id:
        _assert_company_owned(db, company_id, current_user.id)
    redirect_uri = _redirect_uri_for(name)

    state = oauth_state_service.create_state(
        db,
        user_id=current_user.id,
        company_id=company_id,
        capability_name=name,
        redirect_uri=redirect_uri,
    )
    integration = get_integration(capability_def.integration_name)
    url = integration.get_authorization_url(redirect_uri=redirect_uri, state=state)
    return {"url": url}


@router.get("/{name}/callback")
async def oauth_callback(name: str, code: str, state: str, db: Session = Depends(get_db)):
    """Hit directly by the browser on redirect from Google — deliberately
    NOT behind CurrentUser (see module docstring). `state` is how the
    user/company this belongs to is recovered; see oauth_state_service for
    the single-use, expiring validation that makes this safe."""
    capability_def = get_capability(name)
    oauth_row = oauth_state_service.consume_state(db, state=state, capability_name=name)

    integration = get_integration(capability_def.integration_name)
    token_data = await integration.exchange_code_for_token(code, redirect_uri=oauth_row.redirect_uri)

    credential_store.save_credentials(
        db,
        owner_id=oauth_row.user_id,
        company_id=oauth_row.company_id,
        provider=capability_def.integration_name,
        access_token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        extra={"scope": token_data.get("scope")} if token_data.get("scope") else None,
    )
    return RedirectResponse(url=f"{settings.FRONTEND_BASE_URL}/integrations?connected={name}")


@router.delete("/{name}")
def disconnect(
    name: str, current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None)
):
    capability_def = get_capability(name)
    if company_id:
        _assert_company_owned(db, company_id, current_user.id)
    deleted = credential_store.delete_credentials(
        db, owner_id=current_user.id, company_id=company_id, provider=capability_def.integration_name
    )
    return {"deleted": deleted}
