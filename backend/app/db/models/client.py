from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Client(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A client of the active company — used by the Website Builder's
    "Build Client Website" mode so agency-style work is organized under the
    client it's for, with its projects and assets kept separate from the
    company's own. Scoped to a user and (optionally) a company, so switching
    company workspaces re-scopes the visible client list.
    """

    __tablename__ = "clients"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
