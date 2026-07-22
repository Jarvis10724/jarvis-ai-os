"""
Brand Brain service — imports the Primal Penni store into Jarvis's structured,
workspace-scoped source of truth, and serves it to every downstream consumer
(website builder, product pages, emails, social content, research, AI agents).

Read-only w.r.t. Shopify: the import only issues GraphQL *queries* (via
shopify_service, which applies workspace isolation + the capability audit) and
writes exclusively into Jarvis's own brand_* tables. Nothing is ever written
back to the store. Shopify writes stay disabled behind settings.SHOPIFY_WRITE_ENABLED
(False) until explicitly enabled later.

`get_brand_context()` is the canonical accessor — the ONE place consumers read
brand facts from, so websites/emails/agents don't each re-query Shopify.
"""
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.core import shopify_service
from app.db.models.brand_brain import BrandBrain, BrandCollection, BrandProduct

# How many pages (of 50) to walk at most, so a sync can't loop forever.
_MAX_PAGES = 100
_PAGE_SIZE = 50


def _f(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _edges(node: dict, key: str) -> list[dict]:
    return [e["node"] for e in (node.get(key, {}) or {}).get("edges", []) if e.get("node")]


def _parse_product(node: dict) -> dict:
    price = node.get("priceRangeV2") or {}
    mn = price.get("minVariantPrice") or {}
    mx = price.get("maxVariantPrice") or {}
    images = [{"url": i.get("url"), "altText": i.get("altText")} for i in _edges(node, "images")]
    variants = [
        {
            "id": v.get("id"),
            "title": v.get("title"),
            "sku": v.get("sku"),
            "price": _f(v.get("price")),
            "compareAtPrice": _f(v.get("compareAtPrice")),
            "inventoryQuantity": v.get("inventoryQuantity"),
            "availableForSale": v.get("availableForSale"),
            "options": v.get("selectedOptions") or [],
            "image": (v.get("image") or {}).get("url"),
        }
        for v in _edges(node, "variants")
    ]
    return {
        "shopify_id": node.get("id"),
        "title": node.get("title") or "Untitled",
        "handle": node.get("handle"),
        "status": node.get("status"),
        "product_type": node.get("productType"),
        "vendor": node.get("vendor"),
        "description": node.get("description"),
        "tags_json": json.dumps(node.get("tags") or []),
        "price_min": _f(mn.get("amount")),
        "price_max": _f(mx.get("amount")),
        "currency": mn.get("currencyCode") or mx.get("currencyCode"),
        "total_inventory": node.get("totalInventory"),
        "featured_image": (node.get("featuredImage") or {}).get("url"),
        "images_json": json.dumps(images),
        "variants_json": json.dumps(variants),
        "seo_json": json.dumps(node.get("seo") or {}),
    }


def _parse_collection(node: dict) -> dict:
    return {
        "shopify_id": node.get("id"),
        "title": node.get("title") or "Untitled",
        "handle": node.get("handle"),
        "description": node.get("description"),
        "products_count": (node.get("productsCount") or {}).get("count"),
        "image_url": (node.get("image") or {}).get("url"),
    }


def _get_or_create_brain(db: Session, company_id: str) -> BrandBrain:
    brain = db.query(BrandBrain).filter(BrandBrain.company_id == company_id).first()
    if not brain:
        brain = BrandBrain(company_id=company_id, source="shopify")
        db.add(brain)
        db.flush()
    return brain


async def sync_from_shopify(db: Session, *, owner_id: str, company_id: str | None) -> dict:
    """Import the whole catalog + store metadata into the Brand Brain. Walks
    every page of products and collections (read-only), upserts them, prunes
    anything no longer in the store, and records store identity + counts.
    Returns a summary. Never writes to Shopify."""
    # shopify_service enforces "configured + bound to this workspace" and raises
    # a clean ValidationError otherwise — reused here so the guard lives in one place.
    shopify_service._assert_workspace(company_id)
    assert company_id is not None  # guaranteed by _assert_workspace

    brain = _get_or_create_brain(db, company_id)

    # --- Products (paginated) ---
    seen_products: set[str] = set()
    after: str | None = None
    for _ in range(_MAX_PAGES):
        data = await shopify_service.list_products_page(
            db, owner_id=owner_id, company_id=company_id, first=_PAGE_SIZE, after=after
        )
        conn = data.get("products", {}) or {}
        for edge in conn.get("edges", []):
            node = edge.get("node") or {}
            fields = _parse_product(node)
            sid = fields["shopify_id"]
            if not sid:
                continue
            seen_products.add(sid)
            existing = (
                db.query(BrandProduct)
                .filter(BrandProduct.company_id == company_id, BrandProduct.shopify_id == sid)
                .first()
            )
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
            else:
                db.add(BrandProduct(brain_id=brain.id, company_id=company_id, **fields))
        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        after = page.get("endCursor")

    # --- Collections (paginated) ---
    seen_collections: set[str] = set()
    after = None
    for _ in range(_MAX_PAGES):
        data = await shopify_service.list_collections_page(
            db, owner_id=owner_id, company_id=company_id, first=_PAGE_SIZE, after=after
        )
        conn = data.get("collections", {}) or {}
        for edge in conn.get("edges", []):
            node = edge.get("node") or {}
            fields = _parse_collection(node)
            sid = fields["shopify_id"]
            if not sid:
                continue
            seen_collections.add(sid)
            existing = (
                db.query(BrandCollection)
                .filter(BrandCollection.company_id == company_id, BrandCollection.shopify_id == sid)
                .first()
            )
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
            else:
                db.add(BrandCollection(brain_id=brain.id, company_id=company_id, **fields))
        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        after = page.get("endCursor")

    # Prune rows that no longer exist in the store, so the brain is a true mirror.
    if seen_products:
        for p in db.query(BrandProduct).filter(BrandProduct.company_id == company_id).all():
            if p.shopify_id not in seen_products:
                db.delete(p)
    if seen_collections:
        for c in db.query(BrandCollection).filter(BrandCollection.company_id == company_id).all():
            if c.shopify_id not in seen_collections:
                db.delete(c)

    # --- Store metadata ---
    shop = (await shopify_service.get_settings(db, owner_id=owner_id, company_id=company_id)).get("shop", {}) or {}
    brain.store_name = shop.get("name")
    brain.store_domain = shop.get("myshopifyDomain") or settings.SHOPIFY_STORE_DOMAIN
    brain.currency = shop.get("currencyCode")
    brain.plan_name = (shop.get("plan") or {}).get("displayName")
    brain.store_metadata_json = json.dumps(shop)
    brain.product_count = len(seen_products)
    brain.collection_count = len(seen_collections)
    brain.last_synced_at = datetime.now(timezone.utc)

    db.commit()
    return {
        "synced_at": brain.last_synced_at.isoformat(),
        "store_name": brain.store_name,
        "store_domain": brain.store_domain,
        "product_count": brain.product_count,
        "collection_count": brain.collection_count,
        "read_only": True,
        "write_enabled": settings.SHOPIFY_WRITE_ENABLED,
    }


# ---------------------------------------------------------------------------
# Reads — served from Jarvis's own DB (no Shopify round-trip).
# ---------------------------------------------------------------------------


def _brain(db: Session, company_id: str) -> BrandBrain | None:
    return db.query(BrandBrain).filter(BrandBrain.company_id == company_id).first()


def get_summary(db: Session, company_id: str) -> dict:
    brain = _brain(db, company_id)
    if not brain:
        return {"exists": False, "read_only": True, "write_enabled": settings.SHOPIFY_WRITE_ENABLED}
    return {
        "exists": True,
        "source": brain.source,
        "store_name": brain.store_name,
        "store_domain": brain.store_domain,
        "currency": brain.currency,
        "plan_name": brain.plan_name,
        "store_metadata": json.loads(brain.store_metadata_json) if brain.store_metadata_json else {},
        "product_count": brain.product_count,
        "collection_count": brain.collection_count,
        "last_synced_at": brain.last_synced_at.isoformat() if brain.last_synced_at else None,
        "read_only": True,
        "write_enabled": settings.SHOPIFY_WRITE_ENABLED,
    }


def _product_dict(p: BrandProduct) -> dict:
    return {
        "id": p.id,
        "shopify_id": p.shopify_id,
        "title": p.title,
        "handle": p.handle,
        "status": p.status,
        "product_type": p.product_type,
        "vendor": p.vendor,
        "description": p.description,
        "tags": json.loads(p.tags_json) if p.tags_json else [],
        "price_min": p.price_min,
        "price_max": p.price_max,
        "currency": p.currency,
        "total_inventory": p.total_inventory,
        "featured_image": p.featured_image,
        "images": json.loads(p.images_json) if p.images_json else [],
        "variants": json.loads(p.variants_json) if p.variants_json else [],
        "seo": json.loads(p.seo_json) if p.seo_json else {},
    }


def _collection_dict(c: BrandCollection) -> dict:
    return {
        "id": c.id,
        "shopify_id": c.shopify_id,
        "title": c.title,
        "handle": c.handle,
        "description": c.description,
        "products_count": c.products_count,
        "image_url": c.image_url,
    }


def list_products(db: Session, company_id: str, *, limit: int = 100) -> list[dict]:
    rows = (
        db.query(BrandProduct)
        .filter(BrandProduct.company_id == company_id)
        .order_by(BrandProduct.title)
        .limit(limit)
        .all()
    )
    return [_product_dict(p) for p in rows]


def list_collections(db: Session, company_id: str, *, limit: int = 100) -> list[dict]:
    rows = (
        db.query(BrandCollection)
        .filter(BrandCollection.company_id == company_id)
        .order_by(BrandCollection.title)
        .limit(limit)
        .all()
    )
    return [_collection_dict(c) for c in rows]


def get_brand_context(db: Session, company_id: str, *, product_limit: int = 50) -> dict:
    """The canonical brand brief — the default source of truth other features
    (website builder, product pages, emails, social, research, agents) read
    from. Structured facts + a compact text brief for LLM prompt injection.
    Returns exists=False (never raises) when the brain hasn't been synced yet,
    so callers can gracefully fall back."""
    brain = _brain(db, company_id)
    if not brain:
        return {"exists": False, "source_of_truth": "brand_brain", "read_only": True}

    products = list_products(db, company_id, limit=product_limit)
    collections = list_collections(db, company_id)
    tags = sorted({t for p in products for t in p["tags"]})

    lines = [f"Brand: {brain.store_name or 'Unknown'} ({brain.store_domain or ''})"]
    if brain.currency:
        lines.append(f"Currency: {brain.currency}")
    if collections:
        lines.append("Collections: " + ", ".join(c["title"] for c in collections[:20]))
    lines.append("Products:")
    for p in products[:product_limit]:
        price = f"{p['price_min']:.2f}" if p["price_min"] is not None else "?"
        lines.append(f"- {p['title']} ({p['status'] or 'n/a'}) — {price} {p['currency'] or ''}".rstrip())

    return {
        "exists": True,
        "source_of_truth": "brand_brain",
        "read_only": True,
        "store": {
            "name": brain.store_name,
            "domain": brain.store_domain,
            "currency": brain.currency,
            "plan": brain.plan_name,
        },
        "last_synced_at": brain.last_synced_at.isoformat() if brain.last_synced_at else None,
        "counts": {"products": brain.product_count, "collections": brain.collection_count},
        "tags": tags,
        "collections": collections,
        "products": products,
        "brand_brief": "\n".join(lines),
    }
