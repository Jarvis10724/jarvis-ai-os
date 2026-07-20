"""
Server-side OAuth `state` tracking — CSRF protection for the
authorization-code flow (Google today; the same table works for any future
OAuth-based capability).

Why a table instead of a signed-but-stateless token: a signed JWT would
prove the state wasn't forged, but it can't prove the state hasn't already
been *used* — a single-use, server-tracked nonce is what actually stops a
replay of a captured callback URL. `consumed_at` is set the moment the
callback accepts it; a second attempt with the same `state` is rejected
even if it's still within its expiry window.

Deliberately NOT tied to the caller's Bearer token: the browser navigates
away to Google and back as a plain top-level redirect, so no Authorization
header survives the round trip. `state` is how the callback recovers which
user/company initiated the request instead.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OAuthState(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "oauth_states"

    # The actual opaque value sent to Google as `state` and echoed back on
    # the callback — a separate, indexed, unique column rather than reusing
    # `id`, so lookups don't depend on it also being the primary key.
    state: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    capability_name: Mapped[str] = mapped_column(String(50), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(500), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
