"""
Create and consume the single-use `state` value for the OAuth
authorization-code flow — see app.db.models.oauth_state for why this is a
database row rather than a signed token.
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models.oauth_state import OAuthState
from app.exceptions import AuthenticationError

STATE_TTL_MINUTES = 10


def create_state(
    db: Session, *, user_id: str, company_id: str | None, capability_name: str, redirect_uri: str
) -> str:
    token = secrets.token_urlsafe(32)
    row = OAuthState(
        state=token,
        user_id=user_id,
        company_id=company_id,
        capability_name=capability_name,
        redirect_uri=redirect_uri,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES),
    )
    db.add(row)
    db.commit()
    return token


def consume_state(db: Session, *, state: str, capability_name: str) -> OAuthState:
    """Validates and immediately marks the state consumed in one step, so a
    second callback replaying the same `state` (e.g. a captured/retried
    redirect URL) is rejected even inside the expiry window. Raises
    AuthenticationError (never leaks *why* beyond 'invalid or expired' —
    same reasoning as a bad bearer token) for: unknown state, wrong
    capability, expired, or already-consumed."""
    row = db.query(OAuthState).filter(OAuthState.state == state).first()
    if row is None:
        raise AuthenticationError("Invalid or expired OAuth state.")
    if row.capability_name != capability_name:
        raise AuthenticationError("Invalid or expired OAuth state.")
    if row.consumed_at is not None:
        raise AuthenticationError("This OAuth state has already been used.")
    now = datetime.now(timezone.utc)
    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise AuthenticationError("Invalid or expired OAuth state.")

    row.consumed_at = now
    db.commit()
    db.refresh(row)
    return row
