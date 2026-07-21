from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One real business workspace inside Jarvis — Jarvis is a multi-company
    operating system, so a user may own any number of these (Primal Penni is
    the first, not the only one). Each row is a fully isolated workspace:
    its own sections, owner roles, checklists, and products. Common services
    (auth, AI providers, plugins, the integration framework) are shared
    across all companies; nothing here should assume there is only one."""

    __tablename__ = "companies"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Structured workspace metadata (drives modules, AI behavior, branding,
    # and future automations — so Jarvis understands each workspace by data,
    # not just its name). `company_type` is the workspace kind
    # (innovation-hub | consumer-brands | investment | real-estate | venture |
    # business); the frontend's classifyWorkspace prefers it when set and falls
    # back to a name/industry heuristic otherwise. `parent_company_id` models
    # the parent → operating-company relationship (e.g. an innovation hub that
    # owns a consumer brand); it is same-account only, enforced by the API.
    company_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parent_company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    parent: Mapped["Company | None"] = relationship(
        "Company", remote_side="Company.id", foreign_keys=[parent_company_id]
    )
    # Internal categories for organizing work within ONE company (e.g. a
    # holding company's side hustles / consulting / investing / taxes /
    # future-ventures areas). Stored as a JSON list of plain strings —
    # deliberately not a separate table, since these are just labels used to
    # tag/filter records in other modules (projects, CRM, financials), not
    # independent entities with their own data.
    divisions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    owners_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    checklists_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    products: Mapped[list["Product"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single planned/launched product under a Company, with the
    operational fields needed to track it from planning to launch. Numeric
    fields are nullable — they hold real entered data, never fabricated
    placeholder numbers."""

    __tablename__ = "products"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    packaging: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cogs: Mapped[float | None] = mapped_column(nullable=True)  # cost of goods, per unit
    moq: Mapped[int | None] = mapped_column(nullable=True)  # minimum order quantity
    freight: Mapped[float | None] = mapped_column(nullable=True)  # freight cost, per unit
    price: Mapped[float | None] = mapped_column(nullable=True)  # retail price
    margin: Mapped[float | None] = mapped_column(nullable=True)  # percent, 0-100
    inventory: Mapped[int | None] = mapped_column(nullable=True)  # units on hand
    launch_status: Mapped[str] = mapped_column(String(50), default="planning")
    # planning | sourcing | sampling | manufacturing | in_transit | ready | launched
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="products")
