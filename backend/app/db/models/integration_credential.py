from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IntegrationCredential(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores OAuth tokens / API keys for a connected external service, scoped
    to a user and optionally to one company. Jarvis is multi-company, so the
    same provider (e.g. shopify) may be connected once per company with
    isolated credentials — company_id is nullable for credentials that are
    account-wide rather than tied to a single company. Values here should be
    encrypted at rest in production (e.g. via a KMS-backed field encryption
    library) — placeholder column for now."""

    __tablename__ = "integration_credentials"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # email | google_drive | quickbooks | amazon | shopify | social_media
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # provider-specific extras (shop URL, account id, etc.)
