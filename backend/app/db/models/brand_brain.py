"""
Brand Brain — the structured, workspace-scoped source of truth for a business.

A read-only mirror of what's imported from external systems (Shopify first;
Canva/Drive/etc. later), persisted in Jarvis's own DB so every downstream
consumer — website builder, product pages, emails, social content, research,
and AI agents — reads brand facts from ONE canonical place instead of
re-querying each integration ad hoc.

Isolation: every row is bound to a single company_id (the workspace). Nothing
here is ever written back to the source system — importing only reads. Rich,
nested Shopify structures (variants, images, SEO) are kept as JSON on the
product so the schema tolerates Shopify's evolving shape, while the few fields
consumers filter/sort on are promoted to real columns.
"""
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BrandBrain(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One Brand Brain per workspace — store-level identity + sync state."""

    __tablename__ = "brand_brains"
    __table_args__ = (UniqueConstraint("company_id", name="uq_brand_brain_company"),)

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    # Where this brain's data came from (only "shopify" today).
    source: Mapped[str] = mapped_column(String(50), default="shopify")
    store_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    store_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    plan_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Full shop payload (contact email, domains, address, plan) as returned.
    store_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    product_count: Mapped[int] = mapped_column(Integer, default=0)
    collection_count: Mapped[int] = mapped_column(Integer, default=0)

    products: Mapped[list["BrandProduct"]] = relationship(
        back_populates="brain", cascade="all, delete-orphan"
    )
    collections: Mapped[list["BrandCollection"]] = relationship(
        back_populates="brain", cascade="all, delete-orphan"
    )


class BrandProduct(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A product mirrored from the store. Key merchandising fields are columns;
    variants/images/seo/tags keep their full structure as JSON."""

    __tablename__ = "brand_products"
    __table_args__ = (UniqueConstraint("company_id", "shopify_id", name="uq_brand_product_shopify"),)

    brain_id: Mapped[str] = mapped_column(ForeignKey("brand_brains.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    shopify_id: Mapped[str] = mapped_column(String(100), nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    handle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ACTIVE/DRAFT/ARCHIVED
    product_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # list[str]
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    total_inventory: Mapped[int | None] = mapped_column(Integer, nullable=True)
    featured_image: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    images_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # list[{url,altText}]
    variants_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # list[{...}]
    seo_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # {title,description}

    brain: Mapped["BrandBrain"] = relationship(back_populates="products")


class BrandCollection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A collection (product grouping) mirrored from the store."""

    __tablename__ = "brand_collections"
    __table_args__ = (UniqueConstraint("company_id", "shopify_id", name="uq_brand_collection_shopify"),)

    brain_id: Mapped[str] = mapped_column(ForeignKey("brand_brains.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    shopify_id: Mapped[str] = mapped_column(String(100), nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    handle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    products_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    brain: Mapped["BrandBrain"] = relationship(back_populates="collections")
