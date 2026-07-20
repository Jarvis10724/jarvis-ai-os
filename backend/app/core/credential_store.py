"""
The only place that reads or writes IntegrationCredential — every OAuth-based
integration (Gmail today; Calendar/Drive/Shopify/QuickBooks later) goes
through here instead of touching the table directly, so encryption-at-rest
and company scoping are handled in exactly one place.

Tokens are encrypted with app.core.crypto before they ever reach the
database and decrypted only in-process, right before an integration uses
them to call the external API. Nothing here — and nothing upstream of
here — should ever put a raw access_token or refresh_token in an API
response; see api/v1/endpoints/integrations.py and gmail.py, neither of
which serializes an IntegrationCredential row directly.
"""
import json

from sqlalchemy.orm import Session

from app.core.crypto import decrypt, encrypt
from app.db.models.integration_credential import IntegrationCredential


def _find(db: Session, owner_id: str, company_id: str | None, provider: str) -> IntegrationCredential | None:
    q = db.query(IntegrationCredential).filter(
        IntegrationCredential.owner_id == owner_id, IntegrationCredential.provider == provider
    )
    q = q.filter(IntegrationCredential.company_id.is_(None)) if company_id is None else q.filter(
        IntegrationCredential.company_id == company_id
    )
    return q.first()


def save_credentials(
    db: Session,
    *,
    owner_id: str,
    provider: str,
    company_id: str | None = None,
    access_token: str | None = None,
    refresh_token: str | None = None,
    extra: dict | None = None,
) -> IntegrationCredential:
    """Upserts by (owner_id, company_id, provider). `access_token`/
    `refresh_token`/`extra` are only overwritten when a caller actually
    provides a value — a token refresh response often omits `refresh_token`
    (Google only returns it on the first consent), and this must never
    silently null out a still-valid refresh token."""
    cred = _find(db, owner_id, company_id, provider)
    if cred is None:
        cred = IntegrationCredential(owner_id=owner_id, company_id=company_id, provider=provider)
        db.add(cred)

    if access_token is not None:
        cred.access_token = encrypt(access_token)
    if refresh_token is not None:
        cred.refresh_token = encrypt(refresh_token)
    if extra is not None:
        existing = json.loads(cred.extra_json) if cred.extra_json else {}
        existing.update(extra)
        cred.extra_json = json.dumps(existing)

    db.commit()
    db.refresh(cred)
    return cred


def load_credentials(db: Session, *, owner_id: str, company_id: str | None, provider: str) -> dict | None:
    """Returns decrypted {"access_token", "refresh_token", **extra}, or
    None if nothing's connected for this (owner, company, provider).

    Falls back to the account-wide connection (company_id=None) when a
    company-specific one doesn't exist. Most setups have exactly one
    external account (one Gmail/Calendar/Drive login) shared across every
    company workspace — requiring a separate OAuth connection per company
    would mean reconnecting the same account N times for no reason. A
    company-specific connection, if one is ever made, always takes
    priority and is never affected by this fallback (see _find/
    save_credentials — it's a distinct row, looked up first). This also
    means the fallback never leaks a DIFFERENT company's credential:
    `owner_id` is filtered throughout, and the only thing ever fallen back
    to is this same user's own account-wide row, if any."""
    cred = _find(db, owner_id, company_id, provider)
    if cred is None and company_id is not None:
        cred = _find(db, owner_id, None, provider)
    if cred is None:
        return None
    extra = json.loads(cred.extra_json) if cred.extra_json else {}
    return {
        "id": cred.id,
        "access_token": decrypt(cred.access_token),
        "refresh_token": decrypt(cred.refresh_token),
        **extra,
    }


def delete_credentials(db: Session, *, owner_id: str, company_id: str | None, provider: str) -> bool:
    cred = _find(db, owner_id, company_id, provider)
    if cred is None:
        return False
    db.delete(cred)
    db.commit()
    return True
